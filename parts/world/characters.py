"""CARD: characters -- named heroes survive the restart, over a storage PORT.

Same doors as always -- load_character, save_character, put_record, set_rank -- now opening onto the
`CharacterStore` port (adapter character_store_sql) instead of an ORM row directly. This module
builds a `CharacterRecord` from a Session or a casefile and reads it back; it touches no framework.
Derive-don't-store is unchanged: a casefile is a handful of canonical facts; stats and resources
recompute on restore. The merge-save law lives in the port: save_character calls upsert_gameplay
(never rewrites the auth columns), put_record calls upsert_full. See docs/persistence_ports.md.
"""

from __future__ import annotations

import json
from typing import Any

from parts.world import allocate, professions
from parts.world.character_store import CharacterRecord, CharacterStore
from parts.world.job_progress import load_job_progress, save_job_progress
from parts.world.jobs import BASE_HP, BASE_MP, JOBS, bind_calling
from parts.world.progression import hp_gain_per_level, mp_gain_per_level
from parts.world.resources import Resource
from parts.world.session import Session


def _default_store() -> CharacterStore:
    """The default backend: the SQL adapter, imported lazily so this module stays engine-free at
    import time (EXP-003 -- a DB-free `import forge` never pays the ~400ms SQLAlchemy import)."""
    from parts.world.character_store_sql import SqlCharacterStore

    return SqlCharacterStore()


def _serialize_gear(session: Session) -> str:
    """Worn gear as a {slot: {prototype, name, mods}} JSON map, or "" when nothing is equipped.

    We store the PROTOTYPE (the seed label to re-clone) PLUS the instance's rolled name and mods, so
    an AFFIXED drop ('a Cruel blade of the Bear [rare]') survives logout with its rarity intact --
    not just the base weapon. Instances die with the process; this is enough to rebuild them."""
    from parts.world.items import ITEMS, prototype_of

    gear: dict[str, dict[str, Any]] = {}
    for slot, iid in session.equipped.items():
        item = ITEMS.get(iid)
        if item is not None:
            gear[slot] = {
                "prototype": prototype_of(iid),
                "name": item["name"],
                "mods": item["mods"],
                "rarity": item.get("rarity", "common"),
            }
    return json.dumps(gear, sort_keys=True) if gear else ""


def _restore_gear(session: Session, raw: str) -> None:
    """Re-clone and re-equip the gear a character logged out wearing, RESTORING any rolled affixes
    (name + mods). Best-effort, never a crash: an unknown/removed prototype is skipped, and the old
    bare-prototype format (a plain string) still restores the base item (backward-compatible)."""
    if not raw:
        return
    try:
        gear = json.loads(raw)
    except (ValueError, TypeError):
        return
    from parts.world.equipment import SLOTS
    from parts.world.items import ITEMS, PROTOTYPES, clone

    for slot, saved in gear.items():
        if slot not in SLOTS:
            continue
        prototype = saved if isinstance(saved, str) else saved.get("prototype")
        if not isinstance(prototype, str) or prototype not in PROTOTYPES:
            continue
        iid = clone(prototype, "player")
        if isinstance(saved, dict):  # restore the rolled affixes over the fresh base clone
            if isinstance(saved.get("name"), str):
                ITEMS[iid]["name"] = saved["name"]
            if isinstance(saved.get("mods"), dict):
                ITEMS[iid]["mods"] = {k: v for k, v in saved["mods"].items() if isinstance(v, int)}
            if isinstance(saved.get("rarity"), str):
                ITEMS[iid]["rarity"] = saved["rarity"]
        session.equipped[slot] = iid


def _record_to_casefile(record: CharacterRecord) -> dict[str, Any]:
    casefile: dict[str, Any] = {
        "job": record.job,
        "secondary_job": record.secondary_job,
        "level": record.level,
        "xp": record.xp,
        "location": record.location,
        "rank": record.rank,
        "account": record.account,
        "order": record.order,
        "equipped_gear": record.equipped_gear,
        "coins": record.coins,
        "quest_state": record.quest_state,
        "allocated": record.allocated,
        "professions": record.professions,
    }
    if record.auth_salt and record.auth_hash:
        casefile["auth"] = {"salt": record.auth_salt, "hash": record.auth_hash}
    return casefile


def load_character(name: str, store: CharacterStore | None = None) -> dict[str, Any] | None:
    record = (store or _default_store()).find(name)
    return _record_to_casefile(record) if record is not None else None


def put_record(name: str, casefile: dict[str, Any], store: CharacterStore | None = None) -> None:
    """Write one full casefile through the single storage door (auth columns included)."""
    from parts.world.world import START_ROOM

    auth = casefile.get("auth") or {}
    record = CharacterRecord(
        name=name,
        job=casefile.get("job", ""),
        secondary_job=casefile.get("secondary_job", ""),
        level=int(casefile.get("level", 1)),
        xp=int(casefile.get("xp", 0)),
        location=casefile.get("location", START_ROOM),
        rank=casefile.get("rank", "player"),
        account=casefile.get("account", ""),
        order=casefile.get("order", ""),
        equipped_gear=casefile.get("equipped_gear", ""),
        coins=int(casefile.get("coins", 0)),
        quest_state=casefile.get("quest_state", ""),
        allocated=casefile.get("allocated", ""),
        professions=casefile.get("professions", ""),
        auth_salt=auth.get("salt"),
        auth_hash=auth.get("hash"),
    )
    (store or _default_store()).upsert_full(record)


def save_character(session: Session, store: CharacterStore | None = None) -> None:
    """Persist a named hero's gameplay state. Column-scoped update:
    auth fields belong to other cards and are never touched here --
    the merge-save law, enforced by upsert_gameplay (never the auth columns)."""
    if not session.named:
        return
    from parts.world.quest import save_state

    record = CharacterRecord(
        name=session.player_id,
        job=session.job,
        secondary_job=session.secondary_job,
        level=session.level,
        xp=session.xp,
        location=session.location,
        rank=session.rank,
        account=session.account,
        order=session.order,
        equipped_gear=_serialize_gear(session),
        coins=session.coins,
        quest_state=save_state(session.player_id),
        allocated=allocate.serialize(session),
        professions=professions.serialize(session),
    )
    (store or _default_store()).upsert_gameplay(record)
    # Persist per-job progress AFTER the character row exists (the foreign key needs it).
    if session.job_progress:
        save_job_progress(session.player_id, session.job_progress.values())


def restore_character(session: Session, casefile: dict[str, Any]) -> None:
    """Rebuild the full sheet from minimal state. Resources return full:
    logging back in is a night's rest."""
    session.named = True
    session.rank = str(casefile.get("rank", "player"))
    session.account = str(casefile.get("account", ""))
    session.order = str(casefile.get("order", ""))
    session.coins = int(casefile.get("coins", 0))
    session.level = int(casefile["level"])
    session.xp = int(casefile["xp"])
    session.location = str(casefile["location"])
    session.secondary_job = str(casefile.get("secondary_job", ""))
    # A restore is a night's rest: clear transient combat/gear state so a rename into a saved hero
    # can't inherit the prior identity's cooldowns, statuses, or worn gear (which fold into stats).
    session.cooldowns.clear()
    session.statuses.clear()
    session.equipped.clear()
    # ...then re-clone and re-equip THIS hero's own persisted gear (folds back into their stats).
    _restore_gear(session, str(casefile.get("equipped_gear", "")))
    # ...and seed their quest arc back to where they left it, so a story-in-progress survives.
    from parts.world.quest import restore_state

    restore_state(session.player_id, str(casefile.get("quest_state", "")))
    # Load allocated attribute points BEFORE building stats, so bind_calling folds them into the
    # StatBlock (and the HP/MP recompute below includes the allocated stamina/magic).
    allocate.restore(session, str(casefile.get("allocated", "")))
    # Rebuild the maker's trades; level recomputes from practice (derive-don't-store).
    professions.restore(session, str(casefile.get("professions", "")))
    job = str(casefile["job"])
    if not job or job not in JOBS:
        # No calling, or the calling vanished from THIS seed (seeds are games -- a character saved
        # under another seed pack). Restore a jobless sheet and let them re-pick, never crash.
        return
    bind_calling(session, job)
    # Restore every job record this character earned; bind_calling seeded the active one.
    session.job_progress = load_job_progress(session.player_id) or session.job_progress
    assert session.stats is not None
    sta = session.stats.get("stamina").base
    mag = session.stats.get("magic").base
    grown = session.level - 1
    hp_max = BASE_HP + sta + hp_gain_per_level(sta) * grown
    mp_max = BASE_MP + mag + mp_gain_per_level(mag) * grown
    session.resources = {
        "hp": Resource(name="hp", current=hp_max, maximum=hp_max),
        "mp": Resource(name="mp", current=mp_max, maximum=mp_max),
    }


def set_rank(name: str, rank: str, store: CharacterStore | None = None) -> str:
    """Host-shell grant: the bootstrap authority."""
    if (store or _default_store()).set_rank(name, rank):
        return f"{name} is now rank: {rank}."
    return f"No saved character named {name}."
