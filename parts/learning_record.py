"""CARD: learning_record -- capture an engineering improvement as evidence: what changed and why.

The self-improving loop (docs/continuous_improvement.md) ends in LEARN: every meaningful engineering
change should leave a Learning Record so the reasoning, evidence, and tradeoffs are preserved, not
lost in a diff. A record is DATA (a JSON file under data/learning_records/), validated by a loud
gate, with a Markdown projection, so institutional knowledge is git-diffable and browsable. Distinct
from a keel record (human ownership), a pioneer experiment (a bold trial), and a postmortem (an
incident): a Learning Record captures WHY an improvement was made and what Josh should take from it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from parts import record_loader

# Identity is a permanent lowercase kebab/snake label, like a blueprint or part id.
_ID = re.compile(r"^[a-z][a-z0-9_-]*$")


class LearningRecordError(ValueError):
    """A malformed Learning Record: fail loud, never file half-captured knowledge."""


@dataclass(frozen=True)
class LearningRecord:
    """One captured engineering lesson: what changed, why, the evidence, and what to take away."""

    record_id: str
    title: str
    date: str  # ISO date, supplied by the author (no wall-clock in the engine)
    what_changed: str
    why: str
    evidence: tuple[str, ...]
    tradeoffs: str
    future_reuse: str
    concepts: tuple[str, ...]


def _text(raw: dict[str, Any], key: str, rid: str) -> str:
    value = str(raw.get(key, "")).strip()
    if not value:
        raise LearningRecordError(f"learning record {rid!r}: {key!r} is required")
    return value


def _clean_list(raw: Any, key: str, rid: str) -> tuple[str, ...]:
    if not isinstance(raw, list) or not raw:
        raise LearningRecordError(f"learning record {rid!r}: {key!r} must be a non-empty list")
    out: list[str] = []
    for i, item in enumerate(raw):
        text = str(item).strip()
        if not text:
            raise LearningRecordError(f"learning record {rid!r}: {key!r}[{i}] is empty")
        out.append(text)
    return tuple(out)


def from_dict(raw: Any) -> LearningRecord:
    """Validate a raw mapping into a LearningRecord. Every gap fails loud, early, and by name."""
    if not isinstance(raw, dict):
        raise LearningRecordError(f"expected a mapping, got {type(raw).__name__}")
    rid = str(raw.get("record_id", "")).strip()
    if not _ID.match(rid):
        raise LearningRecordError(f"record_id {rid!r} must be lowercase kebab/snake_case")
    return LearningRecord(
        record_id=rid,
        title=_text(raw, "title", rid),
        date=_text(raw, "date", rid),
        what_changed=_text(raw, "what_changed", rid),
        why=_text(raw, "why", rid),
        evidence=_clean_list(raw.get("evidence"), "evidence", rid),
        tradeoffs=_text(raw, "tradeoffs", rid),
        future_reuse=_text(raw, "future_reuse", rid),
        concepts=_clean_list(raw.get("concepts"), "concepts", rid),
    )


def to_markdown(rec: LearningRecord) -> str:
    """The human-readable projection: a lesson a reviewer can read in a diff."""
    lines = [
        f"# {rec.title}",
        "",
        f"- **id:** `{rec.record_id}`",
        f"- **date:** {rec.date}",
        "",
        "## What changed",
        "",
        rec.what_changed,
        "",
        "## Why",
        "",
        rec.why,
        "",
        "## Evidence",
        "",
    ]
    lines += [f"- {item}" for item in rec.evidence]
    lines += [
        "",
        "## Tradeoffs accepted",
        "",
        rec.tradeoffs,
        "",
        "## Future reuse",
        "",
        rec.future_reuse,
    ]
    lines += ["", "## Concepts to understand", ""]
    lines += [f"- {concept}" for concept in rec.concepts]
    return "\n".join(lines) + "\n"


def records_dir(root: Path | None = None) -> Path:
    """Where Learning Records are filed, resolved at call time so tests can point at a tmp dir."""
    base = root if root is not None else Path(__file__).resolve().parent.parent
    return base / "data" / "learning_records"


def load_record(path: Path) -> LearningRecord:
    """Read and validate one Learning Record JSON file (a GATE: a bad file fails loud)."""
    return record_loader.load_record(
        path, from_dict, error=LearningRecordError, label="learning record"
    )


def load_all(root: Path | None = None) -> list[LearningRecord]:
    """Every filed Learning Record, sorted by id. A missing directory is empty, not an error."""
    return record_loader.load_dir(
        records_dir(root), from_dict, error=LearningRecordError, label="learning record"
    )


def learnings(arg: str = "", root: Path | None = None) -> str:
    """The `learnings` verb: browse or read a filed Learning Record."""
    parts = arg.split(maxsplit=1)
    sub = parts[0].lower() if parts else ""
    rest = parts[1].strip() if len(parts) > 1 else ""
    if sub == "show":
        found = next((r for r in load_all(root) if r.record_id == rest), None)
        return to_markdown(found) if found else f"No learning record filed as '{rest}'."
    records = load_all(root)
    if not records:
        return "No learning records filed yet. Capture one under data/learning_records/ (JSON)."
    lines = ["LEARNING RECORDS", ""]
    lines += [f"  {r.record_id:32} {r.title}  ({r.date})" for r in records]
    lines += ["", "  learnings show <id> -- read a record"]
    return "\n".join(lines)
