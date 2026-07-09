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


def load_designations(path: Path) -> list[Designation]:
    """Load one designations file. A missing file is empty, not an error."""
    if not path.exists():
        return []
    data: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise RegistryError(f"{path.name} must be a list of records")
    return [_from_dict(entry) for entry in data]


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
