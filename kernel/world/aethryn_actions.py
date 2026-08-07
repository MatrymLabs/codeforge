"""CARD: aethryn_actions -- validated player mutations declared by Aethryn state packets."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from kernel.world.aethryn_models import ActionOutcome
from kernel.world.aethryn_state import WorldStateStore


def apply_declared_action(
    session: Any,
    command: str,
    argument: str,
    store: WorldStateStore | None,
) -> str:
    """Render the message from one packet-declared reversible action."""
    return apply_declared_action_result(session, command, argument, store).message


def apply_declared_action_result(
    session: Any,
    command: str,
    argument: str,
    store: WorldStateStore | None,
) -> ActionOutcome:
    """Run one packet-declared action and return structured mutation evidence."""
    if store is None:
        return ActionOutcome("unavailable", "No Aethryn world action is available here.")
    requested = argument.strip().casefold()
    actions = _matching_actions(store.schema, command, requested)
    if not actions:
        targets = sorted(
            str(action.get("target", ""))
            for spec in store.schema.values()
            for action in spec.get("actions", [])
            if action.get("command") == command
        )
        if not requested:
            return ActionOutcome(
                "refused", f"Usage: {command} <target> (available: {', '.join(targets) or 'none'})"
            )
        return ActionOutcome(
            "refused", f"No declared {command} action applies to {argument.strip()!r}."
        )
    action, key = actions[0]
    room_id = str(action.get("room_id") or store.schema[key].get("room_id", ""))
    if session.location != room_id:
        return ActionOutcome("refused", f"You must be in {room_id} to do that.", state_key=key)
    required_item = str(action.get("required_item", "")).strip()
    carried_item = _carried_item(session.player_id, required_item) if required_item else ""
    if required_item and not carried_item:
        return ActionOutcome(
            "refused",
            f"You need {required_item.replace('_', ' ')} before you can do that.",
            state_key=key,
        )
    current = store.get(key)
    expected = str(action.get("from", ""))
    if current != expected:
        return ActionOutcome(
            "already",
            str(action.get("already_message", f"The {key} state is already {current}.")),
            state_key=key,
            previous_value=current,
            new_value=current,
        )
    target = str(action.get("to", ""))
    store.set(key, target)
    consumed_item = ""
    if bool(action.get("consume_item", False)) and carried_item:
        from kernel.world.items import ITEMS

        del ITEMS[carried_item]
        consumed_item = carried_item
    return ActionOutcome(
        "changed",
        str(action.get("success_message", f"You set {key} to {target}.")),
        state_key=key,
        previous_value=current,
        new_value=target,
        consumed_item=consumed_item,
    )


def _matching_actions(
    schema: Mapping[str, Mapping[str, Any]], command: str, requested: str
) -> list[tuple[Mapping[str, Any], str]]:
    matches: list[tuple[Mapping[str, Any], str]] = []
    for key, spec in schema.items():
        for action in spec.get("actions", []):
            if action.get("command") != command:
                continue
            names = {str(action.get("target", "")).casefold()}
            names.update(str(alias).casefold() for alias in action.get("aliases", []))
            if requested in names:
                matches.append((action, key))
    return matches


def _carried_item(player_id: str, prototype: str) -> str | None:
    from kernel.world.items import carrier, items_in, prototype_of

    return next(
        (item_id for item_id in items_in(carrier(player_id)) if prototype_of(item_id) == prototype),
        None,
    )
