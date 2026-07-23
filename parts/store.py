"""CARD: store -- the hardware store inventory. List the parts and their purposes.

The store catalog is GENERATED from the code itself: every part
declares 'CARD: <name> -- <purpose>' as the first line of its
docstring. Docs derived from source never go stale.

Two shelves, one store (since the physical extraction):
- parts/shelf/ holds the REUSABLE cores (engine-agnostic Layer 3; poured
  standalone via `make shelf-pour`). These are the actual Hardware Store.
- parts/       holds the ENGINE parts (the platform + world). They import
  the shelf, never the reverse.

The reusable shelf also shows each core's public INTERFACE (its top-level
classes and functions), so the catalog reads like a real parts spec sheet.

Safety note: modules are read with ast, never imported -- listing
the store has zero side effects (no seed load, no world boot).
"""

import ast
from pathlib import Path

PARTS_DIR = Path(__file__).resolve().parent
SHELF_DIR = PARTS_DIR / "shelf"
WORLD_DIR = PARTS_DIR / "world"  # the World Package (Layer 2) is its own subpackage now
TESTS_DIR = PARTS_DIR.parent / "tests"

_CARD_WIDTH = 17


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


def public_interface(path: Path) -> tuple[str, ...]:
    """The module's public API: top-level classes and functions not starting with `_`."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return tuple(
        node.name
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    )


def _stock(directory: Path) -> list[tuple[str, str, str, str]]:
    """Every carded module in a dir as (card_name, tested, purpose, interface), sorted by file."""
    rows: list[tuple[str, str, str, str]] = []
    for path in sorted(directory.glob("*.py")):
        if path.name.startswith("_"):
            continue
        card = inspect_card(path)
        if card is None:
            continue
        name, purpose = card
        tested = "yes" if (TESTS_DIR / f"test_{path.stem}.py").exists() else "NO"
        rows.append((name, tested, purpose, ", ".join(public_interface(path))))
    return rows


def _render(
    title: str, rows: list[tuple[str, str, str, str]], *, show_interface: bool
) -> list[str]:
    header = f"{'#':<4}{'CARD':<{_CARD_WIDTH}}{'TESTED':<8}PURPOSE"
    lines = [title, "-" * len(header), header]
    for number, (name, tested, purpose, interface) in enumerate(rows, start=1):
        lines.append(f"{number:<4}{name:<{_CARD_WIDTH}}{tested:<8}{purpose}")
        if show_interface and interface:
            lines.append(f"    {'':<{_CARD_WIDTH}}-> {interface}")
    return lines


def hardware_store_catalog() -> str:
    """Return the two-shelf parts inventory as display text: reusable cores, then engine parts."""
    shelf = _stock(SHELF_DIR)
    # Engine parts = the platform (parts/) + the World Package (parts/world/), sorted by card.
    engine = sorted(_stock(PARTS_DIR) + _stock(WORLD_DIR))
    lines = ["CODEFORGE HARDWARE STORE", "=" * 24, ""]
    lines += _render(
        "Reusable cores (parts/shelf/ -- engine-agnostic; poured via `make shelf-pour`):",
        shelf,
        show_interface=True,
    )
    lines += [""]
    lines += _render(
        "Engine parts (parts/ -- the platform + world; they import the shelf, never the reverse):",
        engine,
        show_interface=False,
    )
    lines.append(f"\n{len(shelf)} reusable cores + {len(engine)} engine parts stocked.")
    return "\n".join(lines)


if __name__ == "__main__":
    print(hardware_store_catalog())
