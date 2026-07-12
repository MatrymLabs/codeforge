"""CARD: store -- the hardware store inventory. List engine parts and purposes.

The store catalog is GENERATED from the code itself: every part
declares 'CARD: <name> -- <purpose>' as the first line of its
docstring. Docs derived from source never go stale.

Two catalogs, two audiences:
- parts/catalog.py files WORLD content for game operators.
- parts/store.py  files ENGINE parts for developers.

Safety note: modules are read with ast, never imported -- listing
the store has zero side effects (no seed load, no world boot).
"""

import ast
from pathlib import Path

PARTS_DIR = Path(__file__).resolve().parent
TESTS_DIR = PARTS_DIR.parent / "tests"


def inspect_card(path: Path) -> tuple[str, str] | None:
    """Return (card_name, purpose) if the module declares a CARD docstring."""
    doc = ast.get_docstring(ast.parse(path.read_text(encoding="utf-8")))
    if not doc:
        return None
    first = doc.splitlines()[0].strip()
    if not first.startswith("CARD:"):
        return None
    body = first.removeprefix("CARD:").strip()
    name, _, purpose = body.partition("--")
    return (name.strip(), purpose.strip().rstrip("."))


def hardware_store_catalog() -> str:
    """Return the numbered parts inventory as display text."""
    card_width = 13
    header = f"{'#':<4}{'CARD':<{card_width}}{'TESTED':<8}PURPOSE"
    lines = ["CODEFORGE HARDWARE STORE -- engine parts inventory", "", header, "-" * len(header)]
    stocked: list[tuple[str, str, str]] = []
    for path in sorted(PARTS_DIR.glob("*.py")):
        if path.name.startswith("_"):
            continue
        card = inspect_card(path)
        if card is None:
            continue
        name, purpose = card
        tested = "yes" if (TESTS_DIR / f"test_{path.stem}.py").exists() else "NO"
        stocked.append((name, tested, purpose))
    for number, (name, tested, purpose) in enumerate(stocked, start=1):
        lines.append(f"{number:<4}{name:<{card_width}}{tested:<8}{purpose}")
    lines.append(f"\n{len(stocked)} parts stocked.")
    return "\n".join(lines)


if __name__ == "__main__":
    print(hardware_store_catalog())
