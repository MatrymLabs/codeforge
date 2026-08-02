"""CARD: corpus -- a machine-readable record of a coding pattern/smell/rule (find it + change it).

Reverse-engineered from the "CodeForge Corpus" reference catalog (RS-2026-08-01-corpus,
Part 11: the universal pattern/rule record schema). The vision: encode the body of
software-engineering knowledge (GoF/Fowler/EIP/DDD patterns, Fowler's code smells,
CWE/ASVS/Semgrep security rules) as one uniform record so CodeForge becomes a
"translation matrix + parts factory": ingest -> normalize -> transform -> re-emit.

Two honesty fields make this catalog distinctive (the report insists on them):
- `subsumed_by`: the language feature that replaces a pattern (e.g. Strategy ->
  first-class functions), so CodeForge DISCOURAGES over-engineering rather than
  rewarding it (Norvig: Python subsumes 16 of 23 GoF patterns).
- `contested`: a first-class critique for genuinely-debated "laws" (Singleton is an
  anti-pattern; Postel's Law is harmful per RFC 9413; SOLID is criticized as vague).

The schema is stdlib (Record/Corpus operate on objects); `load_yaml` is an optional
convenience for the seed data file.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

# ---- controlled vocabularies (fail loud on an unknown value) ----
CATEGORIES = frozenset(
    {
        "design",
        "architectural",
        "principle",
        "smell",
        "refactoring",
        "rule",
        "idiom",
        "anti_pattern",
    }
)
DETECTION_METHODS = frozenset({"ast_query", "semgrep", "regex", "metric", "dataflow", "manual"})
TRANSFORM_METHODS = frozenset({"mechanical_refactor", "codegen_template", "suggestion", "none"})
# the report's automatability ladder: what CodeForge may do with a record
AUTOMATABILITY = frozenset({"detectable", "transformable", "generatable", "judgment"})


class CorpusError(ValueError):
    """Raised on a malformed record or a duplicate id."""


@dataclass(frozen=True)
class Detection:
    """How CodeForge FINDS the pattern/smell/rule."""

    method: str  # ast_query | semgrep | regex | metric | dataflow | manual
    pattern: str = ""  # a tree-sitter query / semgrep YAML / regex / metric threshold

    def __post_init__(self) -> None:
        if self.method not in DETECTION_METHODS:
            raise CorpusError(f"detection method must be one of {sorted(DETECTION_METHODS)}")


@dataclass(frozen=True)
class Transformation:
    """How CodeForge CHANGES code toward or away from the pattern."""

    method: str  # mechanical_refactor | codegen_template | suggestion | none
    steps: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.method not in TRANSFORM_METHODS:
            raise CorpusError(f"transformation method must be one of {sorted(TRANSFORM_METHODS)}")


@dataclass(frozen=True)
class Contested:
    """A first-class critique for a genuinely-debated practice."""

    is_contested: bool = False
    critique: str = ""
    source: str = ""


@dataclass(frozen=True)
class Record:
    """One uniform pattern/smell/rule record."""

    id: str  # PATTERN.GOF.STRATEGY | SMELL.LONG_METHOD | PRINCIPLE.SOLID | RULE.TAINT.OS_SYSTEM
    category: str
    name: str
    intent: str = ""
    problem: str = ""
    benefits: tuple[str, ...] = ()
    tradeoffs: tuple[str, ...] = ()
    detection: Detection | None = None
    transformation: Transformation | None = None
    subsumed_by: str = ""  # the language feature that replaces it (over-engineering guard)
    anti_pattern_inverse: str = ""  # what abusing/omitting it becomes
    contested: Contested = field(default_factory=Contested)
    automatability: str = "judgment"
    aliases: tuple[str, ...] = ()
    related: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.id or self.id != self.id.upper() or "." not in self.id:
            raise CorpusError(f"id must be a non-empty UPPER.DOTTED key, got {self.id!r}")
        if self.category not in CATEGORIES:
            raise CorpusError(
                f"category must be one of {sorted(CATEGORIES)}, got {self.category!r}"
            )
        if self.automatability not in AUTOMATABILITY:
            raise CorpusError(f"automatability must be one of {sorted(AUTOMATABILITY)}")


class Corpus:
    """A searchable, cross-referenced knowledge store of records (the "Blackboard")."""

    def __init__(self) -> None:
        self._by_id: dict[str, Record] = {}

    def add(self, record: Record) -> None:
        if record.id in self._by_id:
            raise CorpusError(f"duplicate record id: {record.id!r}")
        self._by_id[record.id] = record

    def get(self, record_id: str) -> Record:
        try:
            return self._by_id[record_id]
        except KeyError:
            raise CorpusError(f"unknown record: {record_id!r}") from None

    def all(self) -> tuple[Record, ...]:
        return tuple(self._by_id.values())

    def by_category(self, category: str) -> tuple[Record, ...]:
        return tuple(r for r in self._by_id.values() if r.category == category)

    def contested(self) -> tuple[Record, ...]:
        """Every record with a live critique - what CodeForge must NOT present as settled."""
        return tuple(r for r in self._by_id.values() if r.contested.is_contested)

    def subsumed(self) -> tuple[Record, ...]:
        """Patterns a language feature replaces - CodeForge flags their use as over-engineering."""
        return tuple(r for r in self._by_id.values() if r.subsumed_by)

    def detectable(self) -> tuple[Record, ...]:
        """Records CodeForge can automatically FIND (a real detection signature)."""
        return tuple(r for r in self._by_id.values() if r.detection is not None)

    @classmethod
    def from_records(cls, records: Iterable[Record]) -> Corpus:
        corpus = cls()
        for record in records:
            corpus.add(record)
        return corpus


def _record_from_dict(raw: dict[str, Any]) -> Record:
    det = raw.get("detection")
    trn = raw.get("transformation")
    con = raw.get("contested") or {}
    return Record(
        id=raw["id"],
        category=raw["category"],
        name=raw["name"],
        intent=raw.get("intent", ""),
        problem=raw.get("problem", ""),
        benefits=tuple(raw.get("benefits", ())),
        tradeoffs=tuple(raw.get("tradeoffs", ())),
        detection=Detection(det["method"], det.get("pattern", "")) if det else None,
        transformation=Transformation(trn["method"], tuple(trn.get("steps", ()))) if trn else None,
        subsumed_by=raw.get("subsumed_by", ""),
        anti_pattern_inverse=raw.get("anti_pattern_inverse", ""),
        contested=Contested(
            con.get("is_contested", False), con.get("critique", ""), con.get("source", "")
        ),
        automatability=raw.get("automatability", "judgment"),
        aliases=tuple(raw.get("aliases", ())),
        related=tuple(raw.get("related", ())),
        sources=tuple(raw.get("sources", ())),
    )


def load_yaml(text: str) -> Corpus:
    """Load a seed corpus from a YAML list of record dicts. Requires PyYAML."""
    try:
        import yaml  # optional; the Record/Corpus core is stdlib
    except ImportError as exc:  # pragma: no cover
        raise CorpusError("load_yaml needs PyYAML; build Record objects to stay stdlib") from exc
    data = yaml.safe_load(text)
    if not isinstance(data, list):
        raise CorpusError("a corpus YAML must be a list of records")
    return Corpus.from_records(_record_from_dict(r) for r in data)
