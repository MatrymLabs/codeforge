"""CARD: crafting -- turn gathered materials into goods at the forge (the `craft` verb).

The maker's other half of the loop: a Forger who gathers ember-shards and drowned ingots can forge
them into draughts and gear at the hearth, so the drop/salvage economy and the maker Jobs finally
have a use. Recipes are validated seed data (parts.world.seed.load_recipes). Crafting only consumes
what you hold and mints the output through the item registry -- state stays canonical, mutated by
validated item logic alone; a failed craft spends nothing.
"""

from __future__ import annotations

from parts.world import items
from parts.world.seed import SEED_DIR, load_recipes
from parts.world.session import Session

#: The active seed's recipes, loaded once at import (like a Job's abilities). {} when the seed ships
#: no recipes.yaml -- crafting then reports "nothing to craft here" rather than failing.
RECIPES = load_recipes(SEED_DIR / "recipes.yaml")


def _held(prototype: str) -> list[str]:
    """The inventory instances of this material prototype (a clone counts as the real one)."""
    return [iid for iid in items.items_in("player") if items.prototype_of(iid) == prototype]


def render_recipes(_session: Session) -> str:
    """What the crafter can forge here, with what each needs (the bare `craft` verb)."""
    if not RECIPES:
        return "There is nothing to craft here."
    lines = ["You can forge:"]
    for label, recipe in sorted(RECIPES.items()):
        needs = ", ".join(f"{qty}x {proto}" for proto, qty in sorted(recipe["inputs"].items()))
        lines.append(f"  {recipe['name']} ({label}) -- needs {needs}")
    lines.append("Forge one with:  craft <recipe>")
    return "\n".join(lines)


def craft(session: Session, arg: str) -> str:
    """`craft <recipe>` -- consume a recipe's materials from your hands and forge its output; bare
    `craft` lists what you can make. Fails loud on an unknown recipe or missing materials, and
    spends nothing on failure (the output is minted before any input is consumed, so a bad recipe
    or a full world leaves your materials untouched)."""
    name = arg.strip().lower()
    if not name:
        return render_recipes(session)
    recipe = RECIPES.get(name)
    if recipe is None:
        return f"You know no recipe called '{name}'. Type CRAFT to see what you can forge."
    held = {proto: _held(proto) for proto in recipe["inputs"]}
    short = {p: q - len(held[p]) for p, q in recipe["inputs"].items() if len(held[p]) < q}
    if short:
        lack = ", ".join(f"{count} more {proto}" for proto, count in sorted(short.items()))
        return f"You lack materials to forge {recipe['name']}: need {lack}."
    try:
        made = items.clone(recipe["makes"], "player")  # mint first: nothing is spent if this fails
    except items.ItemError:
        return f"You cannot forge {recipe['name']} right now."
    for proto, qty in recipe["inputs"].items():
        for iid in held[proto][:qty]:
            del items.ITEMS[iid]  # spend the materials only once the output is in hand
    return f"You forge {items.ITEMS[made]['name']} at the hearth."
