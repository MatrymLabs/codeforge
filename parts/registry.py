"""CARD: registry -- the CodeForge Classification Registry filing engine.

A hidden backend catalog beneath the fantasy: every filed object gets a unique
designation (TYPE-UM-SEC-NODE-SEQ-REV) keyed to its frozen runtime label. This card
is the filing engine -- load records, mint the next free designation, validate the
collective. It never renames a label; a designation is additive metadata.

The designation string is canonical: its six structural components are parsed from
it, so the record can never contradict its own id. Records live as JSON under
registry/designations/*.json (schema: registry/schemas/designation.schema.json).
See docs/classification/CLASSIFICATION_SYSTEM.md.
"""

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from parts import loader_cache

_ROOT = Path(__file__).resolve().parent.parent  # the repo root (parts/ -> root)
REGISTRY_DIR = _ROOT / "registry" / "designations"

TYPES = (
    "UM",
    "SEC",
    "RM",
    "NPC",
    "ITM",
    "QST",
    "CMD",
    "MOD",
    "PRT",
    "DOC",
    "PDF",
    "TXT",
    "REG",
    "LSN",
    "QZ",
    "EV",
    "LOG",
    "SYS",
    "API",
)
DOMAINS = tuple(f"UM{n:02d}" for n in range(1, 11))  # UM01..UM10
STATUSES = ("prototype", "active", "hardened", "deprecated", "archived", "superseded")

DESIGNATION_RE = re.compile(
    r"^(?P<type>UM|SEC|RM|NPC|ITM|QST|CMD|MOD|PRT|DOC|PDF|TXT|REG|LSN|QZ|EV|LOG|SYS|API)"
    r"-(?P<domain>UM[0-9]{2})-(?P<sector>S[0-9]{2})-(?P<node>N[0-9]{3})"
    r"-(?P<sequence>[0-9]{3})-(?P<revision>R[0-9]+)$"
)


class RegistryError(ValueError):
    """A designation record is malformed -- fail loud, never file a bad row."""


@dataclass
class Designation:
    """One filed object. The designation is canonical; the six structural fields are
    derived from it in __post_init__, so a record can't disagree with its own id."""

    designation: str
    name: str
    status: str
    function: str
    label: str
    file: str
    # --- derived from the designation (do not set by hand; __post_init__ overwrites) ---
    type: str = ""
    domain: str = ""
    sector: str = "S01"
    node: str = "N001"
    sequence: str = "001"
    revision: str = "R0"
    # --- filing metadata ---
    docs: str = ""
    tests: str = ""
    depends_on: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)
    reuse: str = ""
    tags: list[str] = field(default_factory=list)
    notes: str = ""
    superseded_by: str = ""
    aliases: list[str] = field(default_factory=list)
    created: str = ""
    updated: str = ""

    def __post_init__(self) -> None:
        match = DESIGNATION_RE.match(self.designation)
        if match is None:
            raise RegistryError(f"'{self.designation}' is not a valid designation")
        self.type = match.group("type")
        self.domain = match.group("domain")
        self.sector = match.group("sector")
        self.node = match.group("node")
        self.sequence = match.group("sequence")
        self.revision = match.group("revision")
        if self.domain not in DOMAINS:
            raise RegistryError(f"{self.designation}: domain '{self.domain}' is not a unimatrix")
        if self.status not in STATUSES:
            raise RegistryError(f"{self.designation}: status '{self.status}' not in {STATUSES}")
        for required in ("name", "function", "label", "file"):
            if not str(getattr(self, required)).strip():
                raise RegistryError(f"{self.designation}: '{required}' is required")


def _from_dict(raw: Any) -> Designation:
    if not isinstance(raw, dict):
        raise RegistryError("a designation record must be a mapping")
    fields = set(Designation.__dataclass_fields__)
    unknown = set(raw) - fields
    if unknown:
        raise RegistryError(f"unknown field(s): {', '.join(sorted(unknown))}")
    if "designation" not in raw:
        raise RegistryError("record missing 'designation'")
    return Designation(**{key: value for key, value in raw.items() if key in fields})


def _parse_designations(path: Path) -> list[Designation]:
    """Parse+validate one designations file into records (a bad row raises before caching)."""
    data: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise RegistryError(f"{path.name} must be a list of records")
    return [_from_dict(entry) for entry in data]


def load_designations(path: Path) -> list[Designation]:
    """Load one designations file. A missing file is empty, not an error.

    Parsed once and reused until the file changes on disk, via the shared mtime-guarded
    loader cache (the registry is immutable within a run; the qa-gate self-audit used to
    re-decode every file on every render). Records are read-only for all callers, so the
    cached list is shared, not copied -- the same discipline as the Hardware Store catalog.
    """
    if not path.exists():
        return []
    return loader_cache.load_cached(path, _parse_designations)


def load_collective(registry_dir: Path | None = None) -> list[Designation]:
    """Load every designations/*.json into one collective (the whole registry)."""
    root = registry_dir if registry_dir is not None else REGISTRY_DIR
    if not root.exists():
        return []
    records: list[Designation] = []
    for json_file in sorted(root.glob("*.json")):
        records.extend(load_designations(json_file))
    return records


def save_designations(records: list[Designation], path: Path) -> None:
    """Write records to one designations file (pretty JSON)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(r) for r in records], indent=2), encoding="utf-8")


def _designation_of(item: Designation | str) -> str:
    return item.designation if isinstance(item, Designation) else str(item)


def mint_designation(
    type_: str,
    domain: str,
    existing: list[Designation] | list[str],
    sector: str = "S01",
    node: str = "N001",
) -> str:
    """Mint the next free designation for (type, domain, sector, node). Fills the
    lowest unused sequence, so ids never collide and gaps are reused. Revision R0."""
    if type_ not in TYPES:
        raise RegistryError(f"type '{type_}' not in {TYPES}")
    if domain not in DOMAINS:
        raise RegistryError(f"domain '{domain}' is not a unimatrix")
    used: set[int] = set()
    for item in existing:
        match = DESIGNATION_RE.match(_designation_of(item))
        if (
            match
            and match.group("type") == type_
            and match.group("domain") == domain
            and match.group("sector") == sector
            and match.group("node") == node
        ):
            used.add(int(match.group("sequence")))
    sequence = 1
    while sequence in used:
        sequence += 1
    if sequence > 999:
        raise RegistryError(f"node {type_}-{domain}-{sector}-{node} is full (999 sequences)")
    return f"{type_}-{domain}-{sector}-{node}-{sequence:03d}-R0"


DOMAIN_NAMES = {
    "UM01": "Workshop",
    "UM02": "City",
    "UM03": "Library & Classroom",
    "UM04": "Game systems",
    "UM05": "Hardware Store",
    "UM06": "Compliance & regulations",
    "UM07": "Finance",
    "UM08": "Records management",
    "UM09": "AI & API systems",
    "UM10": "Reports, logs & evidence",
}
TYPE_NAMES = {
    "UM": "Unimatrix",
    "SEC": "Sector",
    "RM": "Room",
    "NPC": "NPC",
    "ITM": "Item",
    "QST": "Quest",
    "CMD": "Command",
    "MOD": "Module",
    "PRT": "Reusable part",
    "DOC": "Document",
    "PDF": "PDF artifact",
    "TXT": "Text analog",
    "REG": "Regulation",
    "LSN": "Lesson",
    "QZ": "Quiz",
    "EV": "Evidence",
    "LOG": "Log",
    "SYS": "System",
    "API": "API connector",
}


def _find(designation: str, records: list[Designation]) -> Designation | None:
    low = designation.lower()
    for r in records:
        if r.designation.lower() == low or low in [a.lower() for a in r.aliases]:
            return r
    return None


def _row(r: Designation) -> str:
    return f"{r.designation:26}{r.status:11}{r.name}"


def registry_list(registry_dir: Path | None = None) -> str:
    """Index the whole collective, grouped by type."""
    records = load_collective(registry_dir)
    if not records:
        return "The registry is empty. File something first."
    by_type: dict[str, int] = {}
    for r in records:
        by_type[r.type] = by_type.get(r.type, 0) + 1
    tally = ", ".join(f"{n}x {t}" for t, n in sorted(by_type.items()))
    lines = [f"Collective registry: {len(records)} designation(s) filed.", tally, ""]
    lines += [_row(r) for r in sorted(records, key=lambda x: x.designation)]
    lines.append("\n`registry show <designation>` for one record.")
    return "\n".join(lines)


def registry_show(designation: str, registry_dir: Path | None = None) -> str:
    """Render one designation's full card (case-insensitive; resolves aliases)."""
    record = _find(designation, load_collective(registry_dir))
    if record is None:
        return f"No designation '{designation}'. Try `registry find` or `registry list`."
    connected = ", ".join(record.related) or "(none)"
    reuse = record.reuse or "(none noted)"
    depends = ", ".join(record.depends_on) or "(none)"
    return "\n".join(
        [
            f"Designation:  {record.designation}",
            f"Name:         {record.name}",
            f"Type:         {TYPE_NAMES.get(record.type, record.type)}",
            f"Domain:       {record.domain} - {DOMAIN_NAMES.get(record.domain, '?')}",
            f"Function:     {record.function}",
            f"Status:       {record.status}",
            f"Files label:  {record.label}   (source: {record.file})",
            f"Depends on:   {depends}",
            f"Connected:    {connected}",
            f"Reuse:        {reuse}",
        ]
    )


def _filtered(records: list[Designation], header: str) -> str:
    if not records:
        return "Nothing filed matches that."
    lines = [header, ""]
    lines += [_row(r) for r in sorted(records, key=lambda x: x.designation)]
    lines.append(f"\n{len(records)} record(s).")
    return "\n".join(lines)


def registry_find(term: str, registry_dir: Path | None = None) -> str:
    """Search designation, name, label, function, and tags for a term."""
    term = term.strip().lower()
    if not term:
        return "Find what? Usage: registry find <term>"
    hits = [
        r
        for r in load_collective(registry_dir)
        if term in f"{r.designation} {r.name} {r.label} {r.function} {' '.join(r.tags)}".lower()
    ]
    return _filtered(hits, f"Designations matching '{term}':")


def registry_type(type_: str, registry_dir: Path | None = None) -> str:
    """List every designation of one type (e.g. RM, NPC, CMD)."""
    type_ = type_.strip().upper()
    hits = [r for r in load_collective(registry_dir) if r.type == type_]
    return _filtered(hits, f"Type {type_} ({TYPE_NAMES.get(type_, '?')}):")


def registry_status(status: str, registry_dir: Path | None = None) -> str:
    """List every designation with one status (e.g. active, prototype)."""
    status = status.strip().lower()
    hits = [r for r in load_collective(registry_dir) if r.status == status]
    return _filtered(hits, f"Status '{status}':")


def validate(
    records: list[Designation], root: Path | None = None, check_files: bool = True
) -> list[str]:
    """Report every filing problem (empty list == clean). No dupes, no orphans, no
    dangling supersedes -- the professional rules, enforced not hoped."""
    problems: list[str] = []
    seen: set[str] = set()
    for r in records:
        if r.designation in seen:
            problems.append(f"duplicate designation: {r.designation}")
        seen.add(r.designation)
    # a runtime label should be filed once per type
    by_type_label: dict[tuple[str, str], list[str]] = {}
    for r in records:
        by_type_label.setdefault((r.type, r.label), []).append(r.designation)
    for (type_, label), ids in by_type_label.items():
        if len(ids) > 1:
            problems.append(f"label '{label}' filed {len(ids)}x under {type_}: {', '.join(ids)}")
    if check_files:
        base = root if root is not None else _ROOT
        for r in records:
            if r.status == "prototype":
                continue  # a prototype isn't built yet -- no source file is expected
            if r.file and not (base / r.file).exists():
                problems.append(f"{r.designation}: file not found: {r.file}")
            if r.tests and not (base / r.tests).exists():
                problems.append(f"{r.designation}: tests not found: {r.tests}")
    for r in records:
        if r.superseded_by and r.superseded_by not in seen:
            problems.append(f"{r.designation}: superseded_by '{r.superseded_by}' is not filed")
    return problems


def unfiled_modules(
    records: list[Designation] | None = None, root: Path | None = None
) -> list[str]:
    """Every importable parts module (incl. subpackages) with NO filed designation.

    Registry completeness -- distinct from validate()'s internal consistency. The registry's
    thesis is that it files the code modules themselves so `qa gate all` audits the codebase;
    an unfiled module is a real gap the internal-consistency check cannot see (it once reported
    CLEAN while 22 modules were undocumented). Empty list == every module is filed.
    """
    base = root if root is not None else _ROOT
    recs = records if records is not None else load_collective()
    filed = {r.file for r in recs if r.file}
    parts_dir = base / "parts"
    if not parts_dir.is_dir():
        return []
    modules = sorted(parts_dir.glob("*.py")) + sorted(parts_dir.glob("*/*.py"))
    unfiled: list[str] = []
    for path in modules:
        if path.name == "__init__.py" or "__pycache__" in path.parts:
            continue
        rel = path.relative_to(base).as_posix()
        if rel not in filed:
            unfiled.append(rel)
    return unfiled
