"""CARD: kernel -- Seed identity + lifecycle: create, run, persist, and recover a Seed as an
addressable entity, independent of any game world.

The recentered platform needs a Seed to be a first-class thing with a stable identity that survives
restart -- not a single global game-data pack selected by an env var. This is the Seed Kernel's
ground floor:

  * `SeedIdentity` -- the immutable facts of one Seed (id, name, owner, purpose, version, created).
  * `BlueprintRecord`   -- identity + mutable lifecycle state (status, runtime session,
    audit trail).
  * `BlueprintStore`    -- the persistence seam (file-backed by default; a fake in tests). This is
    what makes identity survive restart: a fresh kernel over the same store recovers every Seed.
  * `BlueprintKernel`   -- create / get / list / start / stop / archive / status, with owner authz
    on every lifecycle mutation and an audit event appended for each act.

Kept independent of `kernel/world/`: no game import, no `FORGE_SEED`, no world graph. Least
privilege: a non-owner cannot start/stop/archive a Seed. Honest scope: "runtime start" here is
the lifecycle STATE machine + a persisted runtime session; spawning a per-Seed server process is a
later slice (the game case is proven separately by `scripts/deploy_aethryn_seed.py`). The clock and
id-minter are injected, so there is no hidden state and tests are deterministic. Status: PROTOTYPED
(see docs/seed_platform/RECENTERING.md).
"""

from __future__ import annotations

import json
import os
import re
import secrets
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

from kernel.seedlab.safe_path import contained_path, safe_segment
from kernel.shelf.atomic_write import atomic_write_text

# --- lifecycle states + the only legal transitions between them --------------------------------
CREATED = "created"
RUNNING = "running"
STOPPED = "stopped"
ARCHIVED = "archived"
_STATUSES = (CREATED, RUNNING, STOPPED, ARCHIVED)
_TRANSITIONS: dict[str, set[str]] = {
    CREATED: {RUNNING, ARCHIVED},
    RUNNING: {STOPPED},
    STOPPED: {RUNNING, ARCHIVED},
    ARCHIVED: set(),  # a terminal state; an archived Seed does not run again
}

_SLUG = re.compile(r"[^a-z0-9]+")


class BlueprintKernelError(Exception):
    """Base for every Seed Kernel failure. The Kernel fails loud, never mis-states a Seed."""


class SeedNotFound(BlueprintKernelError):  # noqa: N818
    """No Seed with the requested id exists in the store."""


class SeedAuthError(BlueprintKernelError):
    """The actor is not permitted to operate this Seed (least privilege: owner-only for now)."""


class SeedLifecycleError(BlueprintKernelError):
    """An illegal lifecycle transition was requested (e.g. starting an archived Seed)."""


def _utcnow() -> str:
    """Wall clock as an ISO-8601 UTC string. Injected into the Kernel so tests pin a fixed clock."""
    return datetime.now(UTC).isoformat()


def _default_minter(name: str) -> str:
    """Mint a stable, human-legible Seed id: a slug of the name plus a short random suffix."""
    slug = _SLUG.sub("-", name.strip().lower()).strip("-") or "seed"
    return f"seed-{slug}-{secrets.token_hex(3)}"


@dataclass(frozen=True)
class SeedIdentity:
    """The immutable facts of one Seed. Frozen: identity never changes once minted.

    `product_type` and `domain_modules` are the Engineering Form's verdict recorded on the Seed:
    what KIND of Seed this is and which domain modules it selected at creation. They default to
    "" / () so a Seed minted directly (no Form) is still valid, and so a record persisted before
    these fields existed still loads (backward-compatible)."""

    seed_id: str
    name: str
    owner: str
    purpose: str
    version: str = "0.1.0"
    created_at: str = ""
    product_type: str = ""
    domain_modules: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("seed_id", "name", "owner"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise BlueprintKernelError(f"a Seed needs a non-empty {field_name}")  # noqa: TRY003
        # Persisted JSON restores a list; coerce to a tuple so identity stays frozen + hashable.
        object.__setattr__(self, "domain_modules", tuple(self.domain_modules))


@dataclass(frozen=True)
class AuditEvent:
    """One entry in a Seed's tamper-evident lifecycle history."""

    when: str
    actor: str
    action: str
    detail: str = ""


@dataclass(frozen=True)
class BlueprintRecord:
    """A Seed's identity plus its mutable lifecycle state and audit trail. Frozen; the Kernel
    evolves a Seed by persisting a replaced record, so every state change is explicit."""

    identity: SeedIdentity
    status: str = CREATED
    started_at: str = ""  # when the last runtime session began ("" if never)
    stopped_at: str = ""  # when the last runtime session ended
    audit: tuple[AuditEvent, ...] = ()

    def to_dict(self) -> dict:
        """A structured, contract-ready view (the Master Client's fallback is render_status)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> BlueprintRecord:
        """Rebuild a record from persisted JSON, failing loud on a malformed shape."""
        try:
            identity = SeedIdentity(**data["identity"])
            audit = tuple(AuditEvent(**e) for e in data.get("audit", []))
            status = data.get("status", CREATED)
            if status not in _STATUSES:
                raise BlueprintKernelError(f"unknown persisted status {status!r}")  # noqa: TRY003
            return cls(
                identity=identity,
                status=status,
                started_at=data.get("started_at", ""),
                stopped_at=data.get("stopped_at", ""),
                audit=audit,
            )
        except (KeyError, TypeError) as exc:
            raise BlueprintKernelError(f"malformed Seed record: {exc}") from exc  # noqa: TRY003


@runtime_checkable
class BlueprintStore(Protocol):
    """The persistence seam. A file-backed store makes identity survive restart; a test injects a
    fake. The Kernel owns lifecycle; the store owns durability, nothing more."""

    def save(self, record: BlueprintRecord) -> None: ...

    def load(self, seed_id: str) -> BlueprintRecord | None: ...

    def all(self) -> list[BlueprintRecord]: ...


@dataclass
class InMemorySeedStore:
    """A volatile store for tests and ephemeral use. Does NOT survive restart, by design."""

    _records: dict[str, BlueprintRecord] = field(default_factory=dict)

    def save(self, record: BlueprintRecord) -> None:
        self._records[record.identity.seed_id] = record

    def load(self, seed_id: str) -> BlueprintRecord | None:
        return self._records.get(seed_id)

    def all(self) -> list[BlueprintRecord]:
        return list(self._records.values())


@dataclass
class FileSeedStore:
    """A durable store: one JSON file per Seed under `root`. A fresh Kernel over the same `root`
    recovers every Seed -- this is how identity survives restart. Fails loud on a corrupt file."""

    root: Path

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, seed_id: str) -> Path:
        return contained_path(self.root, f"{safe_segment(seed_id, what='seed id')}.json")

    def save(self, record: BlueprintRecord) -> None:
        # Durable atomic write via the shared shelf primitive (no partial record on a crash).
        atomic_write_text(
            self._path(record.identity.seed_id), json.dumps(record.to_dict(), indent=2)
        )

    def load(self, seed_id: str) -> BlueprintRecord | None:
        # CodeQL raises py/path-injection (HIGH) on the read below, because `seed_id` is
        # caller-supplied. It is a FALSE POSITIVE: `_path` runs the id through `safe_segment`
        # (refuses traversal, separators, NUL, absolute, blank) and bounds the result with
        # `contained_path`. CodeQL models neither as a sanitizer.
        #
        # The claim is NOT a bare assertion. tests/test_kernel_path_containment.py drives THIS call
        # site with hostile ids and proves refusal; removing the sanitizer from `_path` turns that
        # file red (measured: 12 failed, 1 passed, the survivor being the calibration case). If the
        # guard goes, the tests shout, which is what makes the dismissal auditable later.
        #
        # The alert is dismissed in the Security tab, NOT suppressed here. An inline
        # `# codeql[py/path-injection]` marker was tried first and does nothing: GitHub code
        # scanning ignores CodeQL inline suppressions. It was removed rather than left in place,
        # because a marker that implies a suppression it does not perform is its own small lie.
        path = self._path(seed_id)
        if not path.is_file():
            return None
        try:
            return BlueprintRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError as exc:
            raise BlueprintKernelError(f"corrupt Seed record {path}: {exc}") from exc  # noqa: TRY003

    def all(self) -> list[BlueprintRecord]:
        out: list[BlueprintRecord] = []
        for path in sorted(self.root.glob("*.json")):
            record = self.load(path.stem)
            if record is not None:
                out.append(record)
        return out


class BlueprintKernel:
    """Owns Seed identity + lifecycle over a store. Every mutation is authorized (owner-only) and
    audited; every state change is persisted immediately, so a restart recovers the exact state."""

    def __init__(
        self,
        store: BlueprintStore,
        *,
        clock: Callable[[], str] = _utcnow,
        id_minter: Callable[[str], str] = _default_minter,
    ) -> None:
        self._store = store
        self._clock = clock
        self._mint = id_minter

    # --- read ----------------------------------------------------------------------------------
    def get(self, seed_id: str) -> BlueprintRecord:
        record = self._store.load(seed_id)
        if record is None:
            raise SeedNotFound(f"no Seed with id {seed_id!r}")  # noqa: TRY003
        return record

    def list_seeds(self) -> list[BlueprintRecord]:
        return self._store.all()

    def status(self, seed_id: str) -> str:
        return render_status(self.get(seed_id))

    # --- create --------------------------------------------------------------------------------
    def create_seed(
        self,
        name: str,
        owner: str,
        purpose: str,
        *,
        seed_id: str | None = None,
        version: str = "0.1.0",
        product_type: str = "",
        domain_modules: tuple[str, ...] = (),
    ) -> BlueprintRecord:
        """Mint a Seed with a stable identity, record it CREATED, and persist it. A caller may pass
        an explicit `seed_id` (deterministic tests); otherwise one is minted from the name.
        `product_type`/`domain_modules` carry the Engineering Form's verdict onto the Seed (empty
        when a Seed is minted directly)."""
        if not name or not name.strip():
            raise BlueprintKernelError("a Seed needs a non-empty name")  # noqa: TRY003
        chosen = seed_id or self._mint(name)
        if self._store.load(chosen) is not None:
            raise BlueprintKernelError(f"a Seed with id {chosen!r} already exists")  # noqa: TRY003
        now = self._clock()
        identity = SeedIdentity(
            seed_id=chosen,
            name=name.strip(),
            owner=owner,
            purpose=purpose,
            version=version,
            created_at=now,
            product_type=product_type,
            domain_modules=tuple(domain_modules),
        )
        record = BlueprintRecord(
            identity=identity,
            status=CREATED,
            audit=(AuditEvent(now, owner, "created", f"Seed {chosen} created"),),
        )
        self._store.save(record)
        return record

    # --- lifecycle -----------------------------------------------------------------------------
    def start(self, seed_id: str, actor: str) -> BlueprintRecord:
        """Deploy the Seed's local runtime: transition to RUNNING, record the session, audit."""
        return self._transition(seed_id, actor, RUNNING, "started", started=True)

    def stop(self, seed_id: str, actor: str) -> BlueprintRecord:
        """Shut the Seed's runtime down: transition to STOPPED, record the session end, audit."""
        return self._transition(seed_id, actor, STOPPED, "stopped", stopped=True)

    def archive(self, seed_id: str, actor: str) -> BlueprintRecord:
        """Retire a Seed: transition to ARCHIVED (terminal), audit. Preserves the record; deletes
        nothing (records are never destroyed by a calendar)."""
        return self._transition(seed_id, actor, ARCHIVED, "archived")

    def reinstate(
        self, record: BlueprintRecord, actor: str, *, detail: str = ""
    ) -> BlueprintRecord:
        """Server-authoritative restore/rollback: write a prior `record` back into the store as the
        Seed's current state, authorized and audited. This is the ONLY sanctioned path back to an
        earlier state, so a backup manager cannot smuggle state past the control plane. Least
        privilege: the actor must own the Seed as it stands now (a restore over an existing Seed is
        checked against the CURRENT owner, not the snapshot's), and a restore may never change a
        Seed's owner. Appends a `reinstated` audit event so the rollback is itself traceable."""
        seed_id = record.identity.seed_id
        current = self._store.load(seed_id)
        if current is not None:
            self._authorize(current, actor)
            if record.identity.owner != current.identity.owner:
                raise SeedAuthError(f"a restore cannot change the owner of Seed {seed_id!r}")  # noqa: TRY003
        else:
            self._authorize(record, actor)
        now = self._clock()
        reinstated = replace(
            record,
            audit=record.audit + (AuditEvent(now, actor, "reinstated", detail),),  # noqa: RUF005
        )
        self._store.save(reinstated)
        return reinstated

    # --- internals -----------------------------------------------------------------------------
    def _transition(
        self,
        seed_id: str,
        actor: str,
        new_status: str,
        action: str,
        *,
        started: bool = False,
        stopped: bool = False,
    ) -> BlueprintRecord:
        record = self.get(seed_id)
        self._authorize(record, actor)
        if new_status not in _TRANSITIONS[record.status]:
            raise SeedLifecycleError(f"cannot {action} a {record.status} Seed (id {seed_id!r})")  # noqa: TRY003
        now = self._clock()
        evolved = replace(
            record,
            status=new_status,
            started_at=now if started else record.started_at,
            stopped_at=now if stopped else record.stopped_at,
            audit=record.audit + (AuditEvent(now, actor, action, f"-> {new_status}"),),  # noqa: RUF005
        )
        self._store.save(evolved)
        return evolved

    @staticmethod
    def _authorize(record: BlueprintRecord, actor: str) -> None:
        """Least privilege: only the Seed's owner may operate it. The Kernel is a control plane."""
        if actor != record.identity.owner:
            raise SeedAuthError(  # noqa: TRY003
                f"actor {actor!r} is not the owner of Seed {record.identity.seed_id!r}"
            )


def render_status(record: BlueprintRecord) -> str:
    """The text fallback the Master Client renders when a structured contract is unavailable: a
    Seed's identity, lifecycle state, and its most recent audit events."""
    i = record.identity
    lines = [
        f"== Seed: {i.name}  [{i.seed_id}] ==",
        f"owner: {i.owner}  version: {i.version}  status: {record.status.upper()}",
        f"purpose: {i.purpose or '-'}",
        f"created: {i.created_at or '-'}  last start: {record.started_at or '-'}  "  # noqa: ISC004
        f"last stop: {record.stopped_at or '-'}",
        "recent activity:",
    ]
    for event in record.audit[-5:]:
        lines.append(f"  {event.when}  {event.actor}  {event.action}  {event.detail}".rstrip())
    return "\n".join(lines)


def _open_kernel(home: str | None = None) -> BlueprintKernel:
    """Open a Kernel over the file store at $SEEDLAB_HOME (default ./.seedlab), for the CLI."""
    root = Path(home or os.environ.get("SEEDLAB_HOME", ".seedlab"))
    return BlueprintKernel(FileSeedStore(root))


def main(argv: list[str] | None = None) -> int:  # noqa: PLR0911
    """CLI: make the Seed lifecycle real and inspectable from the shell (no hidden state).

    Usage:
      python3 -m kernel.seedlab.kernel create <name> <owner> [purpose]
      python3 -m kernel.seedlab.kernel list
      python3 -m kernel.seedlab.kernel status <seed_id>
      python3 -m kernel.seedlab.kernel start|stop|archive <seed_id> <actor>
    """
    import sys  # noqa: PLC0415

    args = list(argv if argv is not None else sys.argv[1:])
    if not args:
        print(main.__doc__)
        return 2
    kernel = _open_kernel()
    cmd, rest = args[0], args[1:]
    try:
        if cmd == "create":
            if len(rest) < 2:  # noqa: PLR2004
                print("usage: create <name> <owner> [purpose]", file=sys.stderr)
                return 2
            record = kernel.create_seed(rest[0], rest[1], rest[2] if len(rest) > 2 else "")  # noqa: PLR2004
            print(f"created {record.identity.seed_id}")
            return 0
        if cmd == "list":
            for record in kernel.list_seeds():
                i = record.identity
                print(f"{i.seed_id}  {record.status.upper():8}  {i.name}  (owner: {i.owner})")
            return 0
        if cmd == "status":
            if not rest:
                print("usage: status <seed_id>", file=sys.stderr)
                return 2
            print(kernel.status(rest[0]))
            return 0
        if cmd in ("start", "stop", "archive"):
            if len(rest) < 2:  # noqa: PLR2004
                print(f"usage: {cmd} <seed_id> <actor>", file=sys.stderr)
                return 2
            record = getattr(kernel, cmd)(rest[0], rest[1])
            print(f"{rest[0]} -> {record.status.upper()}")
            return 0
        print(f"unknown command {cmd!r}", file=sys.stderr)
        return 2  # noqa: TRY300
    except BlueprintKernelError as exc:
        print(f"seed-kernel: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


# Compatibility import for the frozen native contract; new code uses BlueprintKernel.
# contracts/native_seed.py and scripts/native_seed_contract_proof.py import this name and
# are outside this order's allowlist. Codex found this; the order wrongly said the set had
# no public surface, having checked env vars, CLI flags and JSON keys but not contracts/.
SeedKernel = BlueprintKernel
