"""CARD: professions -- the maker's trades: skill tracks leveled by DOING (the `professions` verb).

The calling (jobs.py) is how a hero FIGHTS; a profession is a trade they PRACTICE. Slice 1a gave the
maker a material library and refinement chains; this is slice 1b -- the framework that turns using
those chains into progression. A gather trade (prospecting/mining/herbalism) levels when you gather
a material it works; a craft trade (smithing/leatherworking/alchemy) levels when you craft a recipe
it makes. Skill persists per character; the level recomputes from earned practice on restore
(derive, don't store).

The trades are seed data (seeds/<world>/professions.yaml, validated by kernel.world.seed.
load_professions), so a world declares its own trades -- exactly the kind of proven subsystem the
Seed Platform will later generalise. This module owns only the domain: the reverse lookups (which
trade governs a given material or recipe), the skill curve, and awarding practice. Persistence lives
behind the character store; gather.py and crafting.py call `advance` when a maker does the work.
"""

from __future__ import annotations

from kernel.world.seed import SEED_DIR, load_professions
from kernel.world.session import Session

#: The active seed's trades, loaded once at import (like crafting's RECIPES). {} when the seed ships
#: no professions.yaml -- the maker simply has no trades to practise, and `advance` is a no-op.
PROFESSIONS = load_professions(SEED_DIR / "professions.yaml")

#: The skill curve: PER_LEVEL units of practice per level, capped at LEVEL_CAP. Deliberately simple
#: and legible -- every ten harvests or crafts is a rank, so a maker feels the climb without a
#: grind wall. Level is DERIVED from earned practice, never stored.
PER_LEVEL = 10
LEVEL_CAP = 20


def _reverse(kind: str, field: str) -> dict[str, str]:
    """Build a governed-label -> trade-id lookup for one kind of trade (material or recipe)."""
    out: dict[str, str] = {}
    for pid, prof in PROFESSIONS.items():
        if prof["kind"] == kind:
            for label in prof[field]:  # type: ignore[literal-required]
                out[label] = pid
    return out


#: material prototype -> its gather trade; recipe label -> its craft trade (built from PROFESSIONS).
GATHER_OF = _reverse("gather", "works")
CRAFT_OF = _reverse("craft", "makes")


def level_for(practice: int) -> int:
    """The trade level earned by this much practice: level 1 at zero, +1 every PER_LEVEL, capped."""
    return min(LEVEL_CAP, 1 + max(0, practice) // PER_LEVEL)


def trade_for_gather(material: str) -> str | None:
    """The gather trade that works this material prototype, or None if no trade claims it."""
    return GATHER_OF.get(material)


def trade_for_craft(recipe_label: str) -> str | None:
    """The craft trade that makes this recipe, or None if no trade claims it."""
    return CRAFT_OF.get(recipe_label)


def advance(session: Session, trade_id: str | None) -> str | None:
    """Award one unit of practice to a trade and return a line ONLY when the level ticks up (else
    None -- most practice is silent). A None or unknown trade is a clean no-op, so gather/craft can
    call this unconditionally with whatever `trade_for_*` returns."""
    if not trade_id or trade_id not in PROFESSIONS:
        return None
    before = level_for(session.professions.get(trade_id, 0))
    session.professions[trade_id] = session.professions.get(trade_id, 0) + 1
    after = level_for(session.professions[trade_id])
    if after > before:
        return f"Your {PROFESSIONS[trade_id]['name']} rises to level {after}."
    return None


def render_professions(session: Session) -> str:
    """`professions` -- the maker's trade sheet: every trade, its kind, and this hero's level in it
    (with practice toward the next). Trades never practised show at level 1, so the sheet is a menu
    of what the world offers as much as a record of what you have done."""
    if not PROFESSIONS:
        return "This world knows no trades to practise."
    gather = [p for p in sorted(PROFESSIONS) if PROFESSIONS[p]["kind"] == "gather"]
    craft = [p for p in sorted(PROFESSIONS) if PROFESSIONS[p]["kind"] == "craft"]
    lines = ["Your trades:"]
    for header, ids in (("Gathering", gather), ("Crafting", craft)):
        if not ids:
            continue
        lines.append(f"  {header}:")
        for pid in ids:
            practice = session.professions.get(pid, 0)
            level = level_for(practice)
            tail = "" if level >= LEVEL_CAP else f"  ({practice % PER_LEVEL}/{PER_LEVEL} to next)"
            lines.append(f"    {PROFESSIONS[pid]['name']} -- level {level}{tail}")
    return "\n".join(lines)


def serialize(session: Session) -> str:
    """The character's trades as a compact persisted string: 'trade:practice' pairs, comma-joined.
    Empty string when nothing has been practised (a fresh hero saves no trades)."""
    parts = [f"{pid}:{n}" for pid, n in sorted(session.professions.items()) if n > 0]
    return ",".join(parts)


def restore(session: Session, blob: str) -> None:
    """Rebuild a character's practice from `serialize`'s string. Unknown or malformed pairs are
    dropped (a trade a later seed removed must not crash an old save): forgiving restore."""
    session.professions = {}
    for pair in blob.split(","):
        pid, _, count = pair.partition(":")
        if pid in PROFESSIONS and count.isdigit():
            session.professions[pid] = int(count)
