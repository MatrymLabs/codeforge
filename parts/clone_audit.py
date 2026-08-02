"""CARD: clone_audit -- find duplicate/clone functions across a codebase by content-address.

The "find" front-end of the parts factory. The verifier gate answers "did this transform
preserve behaviour?"; this answers "what is worth transforming?" - it scans a tree of Python
source, content-addresses every function (via the shipped content_address part), and reports
FAMILIES of functions that share a structural address: copy-paste clones, even when their
local names differ. Those families are the natural inputs to a verified extract/rename.

Composes content_address (MOD-05.084) with `normalize_locals=True`, so `def a(x): return x+1`
and `def b(y): return y+1` share one address. Clean-room, stdlib only (`ast`, `textwrap`) plus
that part; NO new dependency.

Honesty contract (inherited from content_address): this is a STRUCTURAL match, not a semantic
one. Two functions with the same address have the same normalized syntax tree - a strong
copy-paste signal - but they are NOT proven equivalent (they may read different globals), and
two functions that compute the same result by different code will NOT share an address. It is
a SUGGEST-ONLY dedup hint for a human to review, never an automatic merge. Trivial functions
are filtered by a statement-count floor so `return None` stubs do not flood the report.
"""

from __future__ import annotations

import ast
import textwrap
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from parts.shelf.content_address import ContentAddressError, content_hash

__all__ = [
    "CloneAuditError",
    "CloneFamily",
    "CloneLocation",
    "CloneReport",
    "find_clones",
    "render",
    "scan_paths",
]

CAVEAT = (
    "STRUCTURAL clone hint, not proof of equivalence: same normalized syntax tree (a strong "
    "copy-paste signal), but functions may read different globals, and different code with the "
    "same result will not match. Review before merging; never auto-dedup."
)


class CloneAuditError(ValueError):
    """Raised on invalid parameters. Unparsable sources are skipped and reported, not raised."""


@dataclass(frozen=True)
class CloneLocation:
    """One function occurrence: where it lives and how big it is."""

    file: str
    name: str
    lineno: int


@dataclass(frozen=True)
class CloneFamily:
    """A group of functions that share one structural content-address."""

    address: str  # first 16 hex chars of the shared content-address
    statements: int  # body size (for ranking; bigger clones matter more)
    members: tuple[CloneLocation, ...]


@dataclass(frozen=True)
class CloneReport:
    """The frozen result of a clone scan."""

    families: tuple[CloneFamily, ...]  # ranked: most members first, then biggest bodies
    functions_scanned: int
    files_scanned: int
    skipped: tuple[str, ...]  # files that failed to parse (name + reason)
    caveat: str = CAVEAT


def _statement_count(node: ast.AST) -> int:
    """Number of statement nodes inside a function (excludes the def itself)."""
    return sum(isinstance(n, ast.stmt) for n in ast.walk(node)) - 1


def find_clones(sources: Mapping[str, str], *, min_statements: int = 3) -> CloneReport:
    """Group the functions across `sources` (file -> text) by structural content-address.

    A function joins a family when another function anywhere shares its address (rename- and
    local-name-invariant). Functions with fewer than `min_statements` body statements are
    skipped as trivial. Unparsable files are recorded in `skipped`, never fatal.
    """
    if min_statements < 1:
        raise CloneAuditError(f"min_statements must be >= 1, got {min_statements}")

    buckets: dict[str, list[CloneLocation]] = {}
    sizes: dict[str, int] = {}
    scanned = 0
    skipped: list[str] = []

    for file, text in sources.items():
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            skipped.append(f"{file}: {exc.msg}")
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if _statement_count(node) < min_statements:
                continue
            segment = ast.get_source_segment(text, node)
            if segment is None:
                continue
            try:
                address = content_hash(textwrap.dedent(segment), normalize_locals=True)
            except ContentAddressError:
                continue  # a segment that will not re-parse standalone (e.g. a decorator quirk)
            scanned += 1
            buckets.setdefault(address, []).append(CloneLocation(file, node.name, node.lineno))
            sizes[address] = _statement_count(node)

    families = [
        CloneFamily(address[:16], sizes[address], tuple(members))
        for address, members in buckets.items()
        if len(members) > 1
    ]
    families.sort(key=lambda fam: (len(fam.members), fam.statements), reverse=True)

    return CloneReport(
        families=tuple(families),
        functions_scanned=scanned,
        files_scanned=len(sources) - len(skipped),
        skipped=tuple(skipped),
    )


def scan_paths(paths: Iterable[Path], *, min_statements: int = 3) -> CloneReport:
    """Read `.py` files under the given paths and run `find_clones`. Unreadable files skip."""
    sources: dict[str, str] = {}
    for path in paths:
        for py in sorted(path.rglob("*.py")) if path.is_dir() else [path]:
            if "__pycache__" in py.parts:
                continue
            try:
                sources[str(py)] = py.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
    return find_clones(sources, min_statements=min_statements)


def render(report: CloneReport) -> str:
    """A human summary: the clone families, ranked, with the caveat attached."""
    lines = [
        f"clone audit: {len(report.families)} clone families across "
        f"{report.functions_scanned} functions in {report.files_scanned} files"
    ]
    for fam in report.families:
        lines.append(f"  [{fam.address}] x{len(fam.members)} ({fam.statements} stmts):")
        for member in fam.members:
            lines.append(f"      {member.file}:{member.lineno} {member.name}")
    if report.skipped:
        lines.append(f"  skipped {len(report.skipped)} unparsable file(s)")
    lines.append(f"  caveat: {report.caveat}")
    return "\n".join(lines)
