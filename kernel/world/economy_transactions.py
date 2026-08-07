"""CARD: economy_transactions -- idempotent item and currency transaction boundary."""

from __future__ import annotations

import json
from collections.abc import MutableMapping, Sequence
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from typing import Literal, Protocol

from kernel.world.aethryn_models import content_digest

TransactionStatus = Literal["committed", "replayed"]


class TransactionError(ValueError):
    """A transaction was invalid, duplicated with different data, or could not commit."""


@dataclass(frozen=True, slots=True)
class CurrencyTransfer:
    """One directed currency leg in a larger atomic transaction."""

    source: str
    destination: str
    amount: int
    reason: str = ""


@dataclass(frozen=True, slots=True)
class ItemTransfer:
    """One directed item-ownership leg in a larger atomic transaction."""

    item_id: str
    source: str
    destination: str


@dataclass(frozen=True, slots=True)
class TransactionRequest:
    """The complete, replay-identifiable request for one value movement."""

    transaction_id: str
    idempotency_key: str
    actor: str
    source: str = ""
    destination: str = ""
    currency_amount: int = 0
    item_ids: tuple[str, ...] = ()
    reason: str = ""
    currency_transfers: tuple[CurrencyTransfer, ...] = ()
    item_transfers: tuple[ItemTransfer, ...] = ()

    @property
    def currency_legs(self) -> tuple[CurrencyTransfer, ...]:
        """Return new multi-leg data, or the original single-leg compatibility shape."""
        if self.currency_transfers:
            return self.currency_transfers
        if self.currency_amount:
            return (
                CurrencyTransfer(self.source, self.destination, self.currency_amount, self.reason),
            )
        return ()

    @property
    def item_legs(self) -> tuple[ItemTransfer, ...]:
        """Return explicit item legs, or translate the original source-owned item list."""
        if self.item_transfers:
            return self.item_transfers
        return tuple(
            ItemTransfer(item_id, self.source, self.destination) for item_id in self.item_ids
        )

    @property
    def request_hash(self) -> str:
        return content_digest(
            {
                "transaction_id": self.transaction_id,
                "idempotency_key": self.idempotency_key,
                "actor": self.actor,
                "source": self.source,
                "destination": self.destination,
                "currency_amount": self.currency_amount,
                "item_ids": self.item_ids,
                "reason": self.reason,
                "currency_transfers": tuple(asdict(leg) for leg in self.currency_legs),
                "item_transfers": tuple(asdict(leg) for leg in self.item_legs),
            }
        )


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    """One signed currency movement attached to a committed transaction."""

    account: str
    delta: int
    balance_after: int
    source: str
    destination: str
    reason: str


@dataclass(frozen=True, slots=True)
class TransactionReceipt:
    """The durable answer returned for both a first request and an exact replay."""

    transaction_id: str
    idempotency_key: str
    request_hash: str
    status: TransactionStatus
    ledger_entries: tuple[LedgerEntry, ...]
    item_transfers: tuple[ItemTransfer, ...] = ()


class TransactionStore(Protocol):
    """Persistence port for committed transaction receipts and ledger entries."""

    def find(self, idempotency_key: str) -> TransactionReceipt | None:
        """Return the receipt for a replay key, if one exists."""
        ...

    def commit(
        self,
        request: TransactionRequest,
        receipt: TransactionReceipt,
    ) -> TransactionReceipt:
        """Persist one receipt atomically or raise without accepting it."""
        ...


class InMemoryTransactionStore:
    """Deterministic transaction store for isolated engine and contract tests."""

    def __init__(self) -> None:
        self._receipts: dict[str, TransactionReceipt] = {}

    def find(self, idempotency_key: str) -> TransactionReceipt | None:
        return self._receipts.get(idempotency_key)

    def commit(
        self,
        request: TransactionRequest,
        receipt: TransactionReceipt,
    ) -> TransactionReceipt:
        existing = self._receipts.get(request.idempotency_key)
        if existing is not None:
            if existing.request_hash != request.request_hash:
                raise TransactionError(
                    f"idempotency key already belongs to a different request: "
                    f"{request.idempotency_key}"
                )
            return existing
        self._receipts[request.idempotency_key] = receipt
        return receipt

    def reset(self) -> None:
        """Clear test state without deleting production records."""
        self._receipts.clear()


class SqlTransactionStore:
    """SQL adapter for receipts and ledger rows; gameplay balances remain caller-owned."""

    def find(self, idempotency_key: str) -> TransactionReceipt | None:
        from kernel.world.db import CurrencyLedgerRow, EconomyTransactionRow, open_archive_session

        with open_archive_session() as session:
            row = (
                session.query(EconomyTransactionRow)
                .filter_by(idempotency_key=idempotency_key)
                .one_or_none()
            )
            if row is None:
                return None
            entries = (
                session.query(CurrencyLedgerRow)
                .filter_by(transaction_id=row.transaction_id)
                .order_by(CurrencyLedgerRow.entry_id)
                .all()
            )
            return self._receipt(row, entries)

    def commit(
        self,
        request: TransactionRequest,
        receipt: TransactionReceipt,
    ) -> TransactionReceipt:
        from kernel.world.db import CurrencyLedgerRow, EconomyTransactionRow, open_archive_session

        with open_archive_session() as session, session.begin():
            existing = (
                session.query(EconomyTransactionRow)
                .filter_by(idempotency_key=request.idempotency_key)
                .one_or_none()
            )
            if existing is not None:
                if existing.request_hash != request.request_hash:
                    raise TransactionError(
                        f"idempotency key already belongs to a different request: "
                        f"{request.idempotency_key}"
                    )
                entries = (
                    session.query(CurrencyLedgerRow)
                    .filter_by(transaction_id=existing.transaction_id)
                    .order_by(CurrencyLedgerRow.entry_id)
                    .all()
                )
                return self._receipt(existing, entries)
            session.add(
                EconomyTransactionRow(
                    transaction_id=request.transaction_id,
                    idempotency_key=request.idempotency_key,
                    request_hash=request.request_hash,
                    actor=request.actor,
                    source=request.source
                    or (request.currency_legs[0].source if request.currency_legs else ""),
                    destination=request.destination
                    or (request.currency_legs[0].destination if request.currency_legs else ""),
                    currency_amount=sum(leg.amount for leg in request.currency_legs),
                    item_ids=json.dumps(
                        {
                            "items": [leg.item_id for leg in request.item_legs],
                            "transfers": [asdict(leg) for leg in request.item_legs],
                        },
                        separators=(",", ":"),
                    ),
                    reason=request.reason,
                    status="committed",
                    created_at=datetime.now(UTC).isoformat(),
                )
            )
            for entry in receipt.ledger_entries:
                session.add(
                    CurrencyLedgerRow(
                        transaction_id=receipt.transaction_id,
                        account=entry.account,
                        delta=entry.delta,
                        balance_after=entry.balance_after,
                        source=entry.source,
                        destination=entry.destination,
                        reason=entry.reason,
                    )
                )
        return receipt

    @staticmethod
    def _receipt(row: object, entries: Sequence[object]) -> TransactionReceipt:
        from kernel.world.db import CurrencyLedgerRow, EconomyTransactionRow

        transaction = row if isinstance(row, EconomyTransactionRow) else None
        if transaction is None:
            raise TransactionError("transaction store returned an invalid transaction row")
        ledger = tuple(
            LedgerEntry(
                account=entry.account,
                delta=entry.delta,
                balance_after=entry.balance_after,
                source=entry.source,
                destination=entry.destination,
                reason=entry.reason,
            )
            for entry in entries
            if isinstance(entry, CurrencyLedgerRow)
        )
        raw_items = getattr(transaction, "item_ids", "[]")
        try:
            decoded_items = json.loads(raw_items or "[]")
        except (TypeError, ValueError):
            decoded_items = []
        decoded_transfers = (
            decoded_items.get("transfers", []) if isinstance(decoded_items, dict) else []
        )
        item_transfers = tuple(
            ItemTransfer(
                item_id=str(item.get("item_id", "")),
                source=str(item.get("source", "")),
                destination=str(item.get("destination", "")),
            )
            for item in decoded_transfers
            if isinstance(item, dict) and item.get("item_id")
        )
        return TransactionReceipt(
            transaction_id=transaction.transaction_id,
            idempotency_key=transaction.idempotency_key,
            request_hash=transaction.request_hash,
            status="committed",
            ledger_entries=ledger,
            item_transfers=item_transfers,
        )


class EconomyTransactionService:
    """Validate and commit one atomic movement across injected wallet and item maps."""

    def __init__(self, store: TransactionStore) -> None:
        self._store = store

    def execute(
        self,
        request: TransactionRequest,
        *,
        wallets: MutableMapping[str, int],
        item_owners: MutableMapping[str, str],
    ) -> TransactionReceipt:
        """Apply a validated transfer once, returning the same result for an exact replay."""
        existing = self._store.find(request.idempotency_key)
        if existing is not None:
            if existing.request_hash != request.request_hash:
                raise TransactionError(
                    f"idempotency key replay changed request data: {request.idempotency_key}"
                )
            return replace(existing, status="replayed")
        self._validate_request(request, wallets, item_owners)

        next_wallets = dict(wallets)
        next_item_owners = dict(item_owners)
        for currency_leg in request.currency_legs:
            if currency_leg.source:
                next_wallets[currency_leg.source] = (
                    next_wallets.get(currency_leg.source, 0) - currency_leg.amount
                )
            if currency_leg.destination:
                next_wallets[currency_leg.destination] = (
                    next_wallets.get(currency_leg.destination, 0) + currency_leg.amount
                )
        for item_leg in request.item_legs:
            next_item_owners[item_leg.item_id] = item_leg.destination
        entries = self._ledger_entries(request, next_wallets)
        receipt = TransactionReceipt(
            transaction_id=request.transaction_id,
            idempotency_key=request.idempotency_key,
            request_hash=request.request_hash,
            status="committed",
            ledger_entries=entries,
            item_transfers=request.item_legs,
        )
        self._store.commit(request, receipt)
        wallets.clear()
        wallets.update(next_wallets)
        item_owners.clear()
        item_owners.update(next_item_owners)
        return receipt

    @staticmethod
    def _validate_request(
        request: TransactionRequest,
        wallets: MutableMapping[str, int],
        item_owners: MutableMapping[str, str],
    ) -> None:
        if not request.transaction_id or not request.idempotency_key:
            raise TransactionError("transaction_id and idempotency_key are required")
        if request.currency_amount < 0:
            raise TransactionError("currency_amount cannot be negative")
        currency_legs = request.currency_legs
        item_legs = request.item_legs
        if not item_legs and not currency_legs:
            raise TransactionError("transaction must move an item or currency")
        if any(leg.amount <= 0 for leg in currency_legs):
            raise TransactionError("currency transfer amounts must be positive")
        if len({leg.item_id for leg in item_legs}) != len(item_legs):
            raise TransactionError("transaction cannot include the same item twice")
        balances = dict(wallets)
        for leg in currency_legs:
            if leg.source and balances.get(leg.source, 0) < leg.amount:
                raise TransactionError("source wallet cannot fund the transaction")
            if leg.source:
                balances[leg.source] = balances.get(leg.source, 0) - leg.amount
            if leg.destination:
                balances[leg.destination] = balances.get(leg.destination, 0) + leg.amount
        missing = [leg.item_id for leg in item_legs if leg.item_id not in item_owners]
        if missing:
            raise TransactionError(f"transaction references unknown items: {', '.join(missing)}")
        misplaced = [leg.item_id for leg in item_legs if item_owners[leg.item_id] != leg.source]
        if misplaced:
            raise TransactionError(
                f"source does not own offered items: {', '.join(sorted(misplaced))}"
            )

    @staticmethod
    def _ledger_entries(
        request: TransactionRequest,
        wallets: MutableMapping[str, int],
    ) -> tuple[LedgerEntry, ...]:
        if not request.currency_legs:
            return ()
        entries: list[LedgerEntry] = []
        for leg in request.currency_legs:
            # balance_after is the final balance after all legs; replay reconciliation can still
            # reconstruct the signed movement from each row and the request hash.
            if leg.source:
                entries.append(
                    LedgerEntry(
                        account=leg.source,
                        delta=-leg.amount,
                        balance_after=wallets[leg.source],
                        source=leg.source,
                        destination=leg.destination,
                        reason=leg.reason or request.reason,
                    )
                )
            if leg.destination:
                entries.append(
                    LedgerEntry(
                        account=leg.destination,
                        delta=leg.amount,
                        balance_after=wallets[leg.destination],
                        source=leg.source,
                        destination=leg.destination,
                        reason=leg.reason or request.reason,
                    )
                )
        return tuple(entries)


def move_currency(
    *,
    transaction_id: str,
    idempotency_key: str,
    actor: str,
    source: str,
    destination: str,
    amount: int,
    reason: str,
    wallets: MutableMapping[str, int],
) -> TransactionReceipt:
    """Commit one currency-only movement through the production SQL receipt store."""
    request = TransactionRequest(
        transaction_id=transaction_id,
        idempotency_key=idempotency_key,
        actor=actor,
        source=source,
        destination=destination,
        currency_amount=amount,
        reason=reason,
    )
    return EconomyTransactionService(SqlTransactionStore()).execute(
        request, wallets=wallets, item_owners={}
    )


def serialize_receipt(receipt: TransactionReceipt) -> str:
    """Serialize a receipt for a durable adapter or audit query."""
    return json.dumps(
        {
            "transaction_id": receipt.transaction_id,
            "idempotency_key": receipt.idempotency_key,
            "request_hash": receipt.request_hash,
            "status": receipt.status,
            "ledger_entries": [asdict(entry) for entry in receipt.ledger_entries],
            "item_transfers": [asdict(item) for item in receipt.item_transfers],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
