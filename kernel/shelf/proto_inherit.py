"""CARD: proto_inherit -- multi-parent prototype inheritance + a prototype-diff for live updates.

Harvested clean-room (pattern-not-code) from Evennia prototypes/spawner.py (BSD-3-Clause). codeforge
today has only a single flat `template:` block per seed file (seed.py) and no way to re-apply an
edited template to already-spawned instances. This adds two authoring powers, as DATA (no in-data
callables - that would fight the "world is data" law, so protfuncs are deliberately NOT harvested):

  1. flatten(name, registry): resolve a prototype's `parent` chain (a str or a LIST of parents,
     merged left-to-right with the child overriding) into one flat dict. Nested dicts (attrs, tags)
     merge structurally; scalars override. Cycles + unknown parents fail loud.
  2. diff(old, new): compute a per-key change plan (KEEP/ADD/UPDATE/REMOVE) between two flattened
     prototypes, so a builder can push a template edit onto live objects deterministically.

Pure functions over plain dicts. Clean-room, stdlib only.
"""

from __future__ import annotations

from typing import Any

KEEP, ADD, UPDATE, REMOVE = "keep", "add", "update", "remove"
_PARENT_KEY = "parent"


class PrototypeError(ValueError):
    """Raised loud on an unknown parent, a parent cycle, or a malformed prototype."""


def _deep_merge(low: dict[str, Any], high: dict[str, Any]) -> dict[str, Any]:
    """Merge `high` over `low`: nested dicts merge structurally, everything else overrides."""
    out = dict(low)
    for key, hv in high.items():
        lv = out.get(key)
        if isinstance(lv, dict) and isinstance(hv, dict):
            out[key] = _deep_merge(lv, hv)
        else:
            out[key] = hv
    return out


def _parents(proto: dict[str, Any]) -> list[str]:
    raw = proto.get(_PARENT_KEY, [])
    if raw == [] or raw is None:
        return []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list) and all(isinstance(p, str) for p in raw):
        return list(raw)
    raise PrototypeError(f"parent must be a str or list of str (got {raw!r})")


def flatten(
    name: str, registry: dict[str, dict[str, Any]], *, _seen: tuple[str, ...] = ()
) -> dict[str, Any]:
    """Resolve `name`'s full inheritance into one flat prototype dict.

    Parents are merged left-to-right (a later parent overrides an earlier one), then the child's own
    keys override all parents. The `parent` key itself is dropped from the result. Raises
    PrototypeError on an unknown prototype or a parent cycle."""
    if name not in registry:
        raise PrototypeError(f"unknown prototype {name!r}")
    if name in _seen:
        raise PrototypeError(f"parent cycle: {' -> '.join((*_seen, name))}")
    proto = registry[name]
    if not isinstance(proto, dict):
        raise PrototypeError(f"prototype {name!r} must be a dict (got {type(proto).__name__})")

    merged: dict[str, Any] = {}
    for parent in _parents(proto):
        merged = _deep_merge(merged, flatten(parent, registry, _seen=(*_seen, name)))
    own = {k: v for k, v in proto.items() if k != _PARENT_KEY}
    merged = _deep_merge(merged, own)
    return merged


def diff(old: dict[str, Any], new: dict[str, Any]) -> dict[str, tuple[str, Any]]:
    """A per-key change plan from `old` to `new`: each key maps to (action, value).

    ADD (key only in new), REMOVE (key only in old, value=old), UPDATE (changed, value=new),
    KEEP (unchanged, value=new). A builder applies this to a live instance deterministically."""
    plan: dict[str, tuple[str, Any]] = {}
    for key in old.keys() | new.keys():
        in_old, in_new = key in old, key in new
        if in_old and not in_new:
            plan[key] = (REMOVE, old[key])
        elif in_new and not in_old:
            plan[key] = (ADD, new[key])
        elif old[key] != new[key]:
            plan[key] = (UPDATE, new[key])
        else:
            plan[key] = (KEEP, new[key])
    return plan


def apply_diff(instance: dict[str, Any], plan: dict[str, tuple[str, Any]]) -> dict[str, Any]:
    """Apply a `diff` plan to a live instance dict, returning a NEW dict (copy-on-write). ADD/UPDATE
    set the value, REMOVE drops the key, KEEP leaves the instance's own value untouched (a player's
    edited field is not clobbered by a KEEP)."""
    out = dict(instance)
    for key, (action, value) in plan.items():
        if action in (ADD, UPDATE):
            out[key] = value
        elif action == REMOVE:
            out.pop(key, None)
    return out
