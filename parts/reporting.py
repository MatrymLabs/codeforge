"""CARD: reporting -- one ReportWriter for dated evidence reports under reports/.

Every saved report (repo-integrity, a frame-up snapshot, future producers) lands under
reports/<category>/ with the same dated-path convention, through one seam. Consolidates
the per-producer mkdir + dated-filename + write pattern so evidence is filed the same way
no matter who produces it. The contents are git-ignored (generated, reproducible); this
writer just keeps the mechanics consistent.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def report_path(
    category: str, root: Path | None = None, stamp: str | None = None, slug: str | None = None
) -> Path:
    """The dated path a report would occupy: reports/<category>/<stamp>[-<slug>].md.
    Creates the category dir if absent. `stamp` defaults to today (injectable for tests)."""
    base = (root or _ROOT) / "reports" / category
    base.mkdir(parents=True, exist_ok=True)
    tag = stamp or date.today().isoformat()
    name = f"{tag}-{slug}.md" if slug else f"{tag}.md"
    return base / name


def write_report(
    category: str,
    text: str,
    root: Path | None = None,
    stamp: str | None = None,
    slug: str | None = None,
) -> Path:
    """Write `text` to the dated report path and return it. Normalizes to one trailing
    newline so every filed report ends the same way."""
    path = report_path(category, root=root, stamp=stamp, slug=slug)
    path.write_text(text.rstrip("\n") + "\n", encoding="utf-8")
    return path
