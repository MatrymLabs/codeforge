"""CARD: crafting -- turn gathered materials into goods at the forge (the `craft` verb).

The maker's other half of the loop: a Forger who gathers ember-shards and drowned ingots can forge
them into draughts and gear at the hearth, so the drop/salvage economy and the maker Jobs finally
have a use. Recipes are validated seed data (kernel.world.seed.load_recipes). Crafting only consumes
what you hold and mints the output through the item registry -- state stays canonical, mutated by
validated item logic alone; a failed craft spends nothing.
"""

from __future__ import annotations

from collections.abc import Mapping

from kernel.world import items
from kernel.world.aethryn_models import content_digest
from kernel.world.economy_transactions import (
    EconomyTransactionService,
    ItemTransfer,
    SqlTransactionStore,
    TransactionError,
    TransactionRequest,
)
from kernel.world.seed import SEED_DIR, load_recipes
from kernel.world.session import Session

#: The active seed's recipes, loaded once at import (like a Job's abilities). {} when the seed ships
#: no recipes.yaml -- crafting then reports "nothing to craft here" rather than failing.
RECIPES = load_recipes(SEED_DIR / "recipes.yaml")

# Rich Aethryn recipes are projected into the same recipe map.  The normal recipe loader remains
# authoritative for legacy-compatible seeds; a seed without material_culture.yaml gets exactly the
# old behavior.
try:
    from kernel.world.material_culture import legacy_recipes, load_catalog

    RECIPES.update(legacy_recipes(load_catalog()))
except (ImportError, ValueError):
    # Non-Aethryn seeds do not carry the optional catalog.  Do not make their existing crafting
    # path depend on an extension file.
    pass


def _held(prototype: str, owner: str) -> list[str]:
    """The `owner`'s inventory instances of this prototype (a clone counts as the real one)."""
    return [iid for iid in items.items_in(owner) if items.prototype_of(iid) == prototype]


def locked_reason(session: Session, recipe: Mapping[str, object]) -> str | None:
    """Why this recipe is beyond the crafter, or None if they may forge it. A gated recipe demands a
    profession LEVEL (slice 1d), a sworn ORDER, and/or a reputation STANDING with that Order; the
    check derives from the player's professions, allegiance, and standing, never a stored flag. An
    ungated recipe is always open."""
    gate = recipe.get("requires")
    if not isinstance(gate, dict):
        return None
    from kernel.world.professions import PROFESSIONS, level_for

    prof = gate.get("profession")
    if isinstance(prof, str):
        level = gate.get("level", 1)
        need = level if isinstance(level, int) else 1
        if level_for(session.professions.get(prof, 0)) < need:
            name = PROFESSIONS[prof]["name"] if prof in PROFESSIONS else prof
            return f"needs {name} level {need}"
    order = gate.get("order")
    if isinstance(order, str):
        from kernel.world.orders import order_name

        if getattr(session, "order", "") != order:
            return f"needs {order_name(order)}"  # order_name already carries 'the'
        standing = gate.get("standing")
        if isinstance(standing, int):
            from kernel.world.reputation import standing_of, tier_for

            if standing_of(session, order) < standing:
                return f"needs standing {tier_for(standing)} with {order_name(order)}"
    return None


def render_recipes(session: Session) -> str:
    """What the crafter can forge here, with what each needs (the bare `craft` verb). A recipe gated
    beyond the crafter still lists, marked with what it takes to earn it, so a maker sees the goal
    (slice 1d)."""
    if not RECIPES:
        return "There is nothing to craft here."
    lines = ["You can forge:"]
    for label, recipe in sorted(RECIPES.items()):
        needs = ", ".join(f"{qty}x {proto}" for proto, qty in sorted(recipe["inputs"].items()))
        locked = locked_reason(session, recipe)
        mark = f"  [locked: {locked}]" if locked else ""
        lines.append(f"  {recipe['name']} ({label}) -- needs {needs}{mark}")
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
    locked = locked_reason(session, recipe)
    if locked:
        return f"You have not earned the craft of {recipe['name']}: it {locked}."
    owner = items.carrier(session.player_id)
    held = {proto: _held(proto, owner) for proto in recipe["inputs"]}
    short = {p: q - len(held[p]) for p, q in recipe["inputs"].items() if len(held[p]) < q}
    if short:
        lack = ", ".join(f"{count} more {proto}" for proto, count in sorted(short.items()))
        return f"You lack materials to forge {recipe['name']}: need {lack}."
    sink = f"room:crafting:{session.player_id}"
    try:
        made = items.clone(recipe["makes"], sink)  # mint first: spent only on success
    except items.ItemError:
        return f"You cannot forge {recipe['name']} right now."
    input_ids = tuple(iid for proto, qty in recipe["inputs"].items() for iid in held[proto][:qty])
    owners = {item_id: item.get("location", "") for item_id, item in items.ITEMS.items()}
    request_id = content_digest(
        {
            "kind": "craft",
            "actor": session.player_id,
            "recipe": name,
            "inputs": input_ids,
            "output": made,
        }
    )[:32]
    request = TransactionRequest(
        transaction_id=f"craft-{request_id}",
        idempotency_key=f"craft-{request_id}",
        actor=session.player_id,
        reason="crafting",
        item_transfers=tuple(
            [
                *(ItemTransfer(iid, items.carrier(session.player_id), sink) for iid in input_ids),
                ItemTransfer(made, sink, items.carrier(session.player_id)),
            ]
        ),
    )
    try:
        EconomyTransactionService(SqlTransactionStore()).execute(
            request, wallets={}, item_owners=owners
        )
    except TransactionError as exc:
        items.ITEMS.pop(made, None)
        return f"You cannot forge {recipe['name']} right now: {exc}."
    for iid in input_ids:
        del items.ITEMS[
            iid
        ]  # receipt records the consumed input before it leaves the live registry
    items.ITEMS[made]["location"] = items.carrier(session.player_id)
    line = f"You forge {items.ITEMS[made]['name']} at the hearth."
    # Forging advances the craft trade that makes this recipe (smithing/alchemy/leatherworking);
    # a rank-up appends its own line, a no-op is silent (kernel.world.professions).
    from kernel.world.professions import advance, trade_for_craft

    rose = advance(session, trade_for_craft(name))
    if rose:
        line = f"{line}\n{rose}"
    # Story arcs may observe the same successful recipe without owning crafting state. Crafting
    # remains authoritative for the transaction; the quest engine only applies its declared effect.
    from kernel.world import quest

    quest_line = quest.on_event(session, "craft", name)
    if quest_line:
        line = f"{line}\n{quest_line}"
    return line
