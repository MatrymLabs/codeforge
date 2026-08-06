"""Bounded, structured audit records for script execution and capability calls."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from kernel.shelf.atomic_write import atomic_write_text


@dataclass(frozen=True)
class ScriptAuditRecord:
    event_id: str
    script_id: str
    source_revision: int
    seed_id: str
    sandbox_id: str
    invocation_cause: str
    result: str
    correlation_id: str
    capabilities: tuple[str, ...] = ()
    resource_budget: dict[str, object] = field(default_factory=dict)
    resource_used: dict[str, object] = field(default_factory=dict)
    host_calls: int = 0
    state_changes: int = 0
    output_summary: str = ""
    exception_fingerprint: str | None = None
    when: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def __post_init__(self) -> None:
        if not self.event_id.strip() or not self.script_id.strip() or not self.seed_id.strip():
            raise ValueError("audit identity fields must not be empty")
        if self.host_calls < 0 or self.state_changes < 0:
            raise ValueError("audit counters must not be negative")
        object.__setattr__(self, "capabilities", tuple(self.capabilities))
        object.__setattr__(self, "output_summary", self.output_summary[:2048])

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class AuditLedger:
    """Append-only JSONL ledger with duplicate event detection and bounded output."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else None
        self._records: list[ScriptAuditRecord] = []
        self._ids: set[str] = set()
        if self.path is not None:
            self._load()

    def _load(self) -> None:
        if self.path is None or not self.path.is_file():
            return
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
            for line in lines:
                raw = json.loads(line)
                record = ScriptAuditRecord(**raw)
                self.append(record, persist=False)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ValueError(f"cannot load script audit ledger {self.path}: {exc}") from exc

    def append(self, record: ScriptAuditRecord, *, persist: bool = True) -> None:
        if record.event_id in self._ids:
            raise ValueError(f"duplicate audit event: {record.event_id}")
        self._ids.add(record.event_id)
        self._records.append(record)
        if persist and self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            content = "".join(
                json.dumps(item.to_dict(), sort_keys=True) + "\n" for item in self._records
            )
            atomic_write_text(self.path, content)

    def records(self) -> tuple[ScriptAuditRecord, ...]:
        return tuple(self._records)
