"""CARD: ledger -- a double-entry ledger: money is conserved, it only moves, and a retry is safe.

The reusable core behind correct money movement, reconstructed from the publicly documented design
of TigerBeetle (a purpose-built double-entry accounting database) fused with Stripe's idempotency
model. The single guarantee: **every transfer posts an equal debit and credit**, so across the whole
ledger the sum of all debits always equals the sum of all credits. Money is never created or
destroyed; it only moves between accounts. That invariant is the point -- a single-entry balance
(add here, subtract there, hope they match) can drift; double-entry cannot, by construction.

What it does:

- **Open accounts** with optional guard flags (an account that may not go overdrawn).
- **Post transfers** (an amount from a debit account to a credit account) into an append-only,
  immutable log. A transfer's id is unique -- re-posting the same id is refused.
- **Guarantee conservation:** `total_debits() == total_credits()` after any sequence of transfers.
- **Make retries safe:** an optional idempotency key runs a post at most once and replays the
  original posted transfer on retry (the `idempotency` shelf core), so a network retry or a
  double-submit never double-applies.

Fail-loud: an unknown account, a non-positive amount, a self-transfer, a duplicate transfer id, or
an overdraft on a guarded account is refused BEFORE any balance moves -- a rejected transfer leaves
the ledger exactly as it was. Amounts are non-negative integers in the smallest unit (never floats;
money is not a float), so this composes directly with the game's integer coinage.

This is an ORIGINAL, self-contained part. It does not touch the game's canonical single-entry
economy (`parts/world/coinage.py`); wiring it in as an audit mirror or the system of record is a
separate, human-approved decision (see docs/design/double_entry_ledger.md).

Provenance: original implementation. The double-entry account/transfer schema and the
`debits_must_not_exceed_credits` guard are the publicly documented TigerBeetle model; the
idempotency-key retry semantics are the publicly documented Stripe model. No code copied; not
affiliated with or endorsed by either project.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from parts.shelf.idempotency import IdempotencyStore


class LedgerError(ValueError):
    """A rule was broken (unknown account, bad amount, duplicate id, overdraft): refuse before any
    balance moves. A rejected transfer leaves the ledger exactly as it was."""


@dataclass
class Account:
    """One account: its posted totals and its optional overdraft guards.

    The ledger is neutral about account *type* (asset vs liability): it tracks both sides and lets
    the caller interpret the sign of `balance()`. `debits_posted`/`credits_posted` are mutated only
    by a validated `Ledger.post_transfer` (canonical state, one door), never set by hand.
    """

    id: str
    debits_posted: int = 0
    credits_posted: int = 0
    # Guards (TigerBeetle account flags): reject a transfer that would push this account past the
    # other side. A wallet that may never go negative sets debits_must_not_exceed_credits.
    debits_must_not_exceed_credits: bool = False
    credits_must_not_exceed_debits: bool = False

    @property
    def balance(self) -> int:
        """The neutral balance: debits minus credits. An asset account reads this as its balance; a
        liability account reads its balance as the negation. The ledger stays type-agnostic."""
        return self.debits_posted - self.credits_posted


@dataclass(frozen=True)
class Transfer:
    """One immutable posting: `amount` moved from `debit_account_id` to `credit_account_id`.

    Frozen: a posted transfer is history and never changes. Corrections are new, compensating
    transfers, never edits -- the append-only log is the audit trail.
    """

    id: str
    debit_account_id: str
    credit_account_id: str
    amount: int


@dataclass
class Ledger:
    """A double-entry ledger: accounts, an append-only transfer log, and the conservation invariant.

    In-memory and single-process (the engine tick is single-threaded). A networked deployment fronts
    the same contract with a transactional store: the transfer log is an INSERT with a UNIQUE
    transfer id, and the two balance updates plus the insert commit in ONE database transaction so a
    crash can never leave a half-posted transfer. See the design doc for that boundary.
    """

    _accounts: dict[str, Account] = field(default_factory=dict)
    _transfers: list[Transfer] = field(default_factory=list)
    _idem: IdempotencyStore[Transfer] = field(default_factory=IdempotencyStore)

    # --- accounts ----------------------------------------------------------------------------

    def open_account(
        self,
        account_id: str,
        *,
        debits_must_not_exceed_credits: bool = False,
        credits_must_not_exceed_debits: bool = False,
    ) -> Account:
        """Open a new zero-balance account. A blank or duplicate id is refused."""
        if not account_id or not account_id.strip():
            raise LedgerError("an account id must be a non-empty string")
        if account_id in self._accounts:
            raise LedgerError(f"account {account_id!r} already exists")
        account = Account(
            id=account_id,
            debits_must_not_exceed_credits=debits_must_not_exceed_credits,
            credits_must_not_exceed_debits=credits_must_not_exceed_debits,
        )
        self._accounts[account_id] = account
        return account

    def account(self, account_id: str) -> Account:
        """The account, or `LedgerError` if it was never opened."""
        try:
            return self._accounts[account_id]
        except KeyError as exc:
            raise LedgerError(f"unknown account {account_id!r}") from exc

    def balance(self, account_id: str) -> int:
        """The neutral balance (debits minus credits) of an opened account."""
        return self.account(account_id).balance

    # --- transfers ---------------------------------------------------------------------------

    def post_transfer(
        self,
        transfer_id: str,
        debit_account_id: str,
        credit_account_id: str,
        amount: int,
        *,
        idempotency_key: str | None = None,
    ) -> Transfer:
        """Post `amount` from the debit account to the credit account into the immutable log.

        With an `idempotency_key`, the post runs at most once for that key: a retry with the same
        key and the same (accounts, amount, id) replays the original transfer without moving any
        balance again; the same key with different parameters raises (via the idempotency core).
        Without a key, a duplicate `transfer_id` is still refused. Any rule violation raises
        `LedgerError` before a single balance moves.
        """
        if idempotency_key is None:
            return self._do_post(transfer_id, debit_account_id, credit_account_id, amount)
        fingerprint = f"{transfer_id}|{debit_account_id}|{credit_account_id}|{amount}"
        outcome = self._idem.remember(
            idempotency_key,
            fingerprint,
            lambda: self._do_post(transfer_id, debit_account_id, credit_account_id, amount),
        )
        return outcome.result

    def _do_post(
        self, transfer_id: str, debit_account_id: str, credit_account_id: str, amount: int
    ) -> Transfer:
        """Validate every rule, then apply the double posting. Validation happens BEFORE any
        mutation, so a refusal leaves the ledger untouched."""
        if not transfer_id or not transfer_id.strip():
            raise LedgerError("a transfer id must be a non-empty string")
        if not isinstance(amount, int) or isinstance(amount, bool):
            raise LedgerError(f"amount must be an int (smallest unit), got {amount!r}")
        if amount <= 0:
            raise LedgerError(f"a transfer must move a positive amount, got {amount}")
        if debit_account_id == credit_account_id:
            raise LedgerError(
                f"a transfer cannot debit and credit the same account ({debit_account_id!r})"
            )
        if any(t.id == transfer_id for t in self._transfers):
            raise LedgerError(f"transfer id {transfer_id!r} was already posted")
        debit = self.account(debit_account_id)  # raises LedgerError if unknown
        credit = self.account(credit_account_id)  # raises LedgerError if unknown

        # Overdraft guards, checked before applying (TigerBeetle account flags).
        if (
            debit.debits_must_not_exceed_credits
            and debit.debits_posted + amount > debit.credits_posted
        ):
            raise LedgerError(
                f"transfer would overdraw {debit_account_id!r}: debits "
                f"{debit.debits_posted + amount} would exceed credits {debit.credits_posted}"
            )
        if (
            credit.credits_must_not_exceed_debits
            and credit.credits_posted + amount > credit.debits_posted
        ):
            raise LedgerError(
                f"transfer would overdraw {credit_account_id!r}: credits "
                f"{credit.credits_posted + amount} would exceed debits {credit.debits_posted}"
            )

        # Apply: the two equal postings that make this double-entry (conservation by construction).
        debit.debits_posted += amount
        credit.credits_posted += amount
        transfer = Transfer(
            id=transfer_id,
            debit_account_id=debit_account_id,
            credit_account_id=credit_account_id,
            amount=amount,
        )
        self._transfers.append(transfer)
        return transfer

    # --- views (read-only projections) -------------------------------------------------------

    def transfers(self) -> tuple[Transfer, ...]:
        """The append-only transfer log, oldest first (an immutable snapshot)."""
        return tuple(self._transfers)

    def total_debits(self) -> int:
        """The sum of every account's posted debits."""
        return sum(a.debits_posted for a in self._accounts.values())

    def total_credits(self) -> int:
        """The sum of every account's posted credits."""
        return sum(a.credits_posted for a in self._accounts.values())

    def assert_balanced(self) -> None:
        """Fail loud if the double-entry invariant is ever violated (it cannot be, by construction;
        this is a defensive check for tests and reconciliation)."""
        if self.total_debits() != self.total_credits():
            raise LedgerError(
                f"ledger is not balanced: total debits {self.total_debits()} "
                f"!= total credits {self.total_credits()}"
            )
