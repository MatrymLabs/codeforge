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

from kernel.world import allocate, professions, reputation
from kernel.world import friends as friends_mod
from kernel.world import lockouts as lockouts_mod
from kernel.world.character_store import CharacterRecord, CharacterStore
from kernel.world.job_progress import load_job_progress, save_job_progress
from kernel.world.jobs import BASE_HP, BASE_MP, JOBS, bind_calling
from kernel.world.progression import hp_gain_per_level, mp_gain_per_level
from kernel.world.resources import Resource
from kernel.world.session import Session


def _default_store() -> CharacterStore:
    """The default backend: the SQL adapter, imported lazily so this module stays engine-free at
    import time (EXP-003 -- a DB-free `import forge` never pays the ~400ms SQLAlchemy import)."""
    from kernel.world.character_store_sql import SqlCharacterStore

    return SqlCharacterStore()


def snapshot_item(iid: str) -> dict[str, Any] | None:
    """A persistable snapshot of one live item instance: its PROTOTYPE (the seed label to re-clone)
    plus the instance's rolled name, mods, and rarity, so an AFFIXED drop ('a Cruel blade of the
    Bear [rare]') survives logout with its roll intact, not just the base item. None if the id names
    no live item. The one shape both worn gear and loose inventory persist through."""
    from kernel.world.items import ITEMS, prototype_of

    item = ITEMS.get(iid)
    if item is None:
        return None
    snap: dict[str, Any] = {
        "prototype": prototype_of(iid),
        "name": item["name"],
        "mods": item["mods"],
        "rarity": item.get("rarity", "common"),
    }
    if item.get("slot"):  # only gear wears; carry its durability so wear survives logout
        from kernel.world.durability import current as _durability

        snap["durability"] = _durability(iid)
    return snap


def reclone_item(snapshot: Any, carrier_tag: str) -> str | None:
    """Re-mint a snapshotted item into a carrier, restoring its rolled affixes over a fresh base
    clone. Accepts the legacy bare-prototype string too (backward-compatible). None (skipped, not a
    crash) if the prototype is unknown or has been retired from the seed."""
    from kernel.world.items import ITEMS, PROTOTYPES, clone

    if isinstance(snapshot, str):
        prototype: Any = snapshot
    elif isinstance(snapshot, dict):
        prototype = snapshot.get("prototype")
    else:
        return None
    if not isinstance(prototype, str) or prototype not in PROTOTYPES:
        return None
    iid = clone(prototype, carrier_tag)
    if isinstance(snapshot, dict):  # restore the rolled affixes over the fresh base clone
        if isinstance(snapshot.get("name"), str):
            ITEMS[iid]["name"] = snapshot["name"]
        if isinstance(snapshot.get("mods"), dict):
            ITEMS[iid]["mods"] = {k: v for k, v in snapshot["mods"].items() if isinstance(v, int)}
        if isinstance(snapshot.get("rarity"), str):
            ITEMS[iid]["rarity"] = snapshot["rarity"]
        if isinstance(snapshot.get("durability"), int):  # restore any accrued wear
            ITEMS[iid]["durability"] = snapshot["durability"]
    return iid


def _serialize_gear(session: Session) -> str:
    """Worn gear as a {slot: {prototype, name, mods, rarity}} JSON map, or "" when nothing is
    equipped. Instances die with the process; a snapshot per slot is enough to rebuild them."""
    gear: dict[str, dict[str, Any]] = {}
    for slot, iid in session.equipped.items():
        snap = snapshot_item(iid)
        if snap is not None:
            gear[slot] = snap
    return json.dumps(gear, sort_keys=True) if gear else ""


def _restore_gear(session: Session, raw: str) -> None:
    """Re-clone and re-equip the gear a character logged out wearing, restoring any rolled affixes.
    Best-effort, never a crash: an unknown slot or retired prototype is skipped."""
    if not raw:
        return
    try:
        gear = json.loads(raw)
    except (ValueError, TypeError):
        return
    from kernel.world.equipment import SLOTS
    from kernel.world.items import carrier

    for slot, saved in gear.items():
        if slot not in SLOTS:
            continue
        iid = reclone_item(saved, carrier(session.player_id))
        if iid is not None:
            session.equipped[slot] = iid


def _snapshot_loose(session: Session) -> list[dict[str, Any]]:
    """Every LOOSE item a hero carries (in the bag, not worn) as snapshots. Worn gear is excluded on
    purpose: it persists on the character row via _serialize_gear, so a snapshot here would double
    it. loose = the items tagged to this hero's carrier, minus the ones currently equipped."""
    from kernel.world.items import carrier, items_in

    equipped = set(session.equipped.values())
    bag: list[dict[str, Any]] = []
    for iid in items_in(carrier(session.player_id)):
        if iid in equipped:
            continue
        snap = snapshot_item(iid)
        if snap is not None:
            bag.append(snap)
    return bag


def _clear_carrier(player_id: str) -> None:
    """Drop every item currently tagged to a hero's carrier from the live ITEMS map. Called before a
    restore re-clones from storage, so a reconnect in the same process can never DUPLICATE a bag by
    stacking freshly-cloned items on top of the previous session's orphaned instances."""
    from kernel.world.items import ITEMS, carrier, items_in

    for iid in items_in(carrier(player_id)):
        ITEMS.pop(iid, None)


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
        "guild": record.guild,
        "guild_rank": record.guild_rank,
        "equipped_gear": record.equipped_gear,
        "coins": record.coins,
        "quest_state": record.quest_state,
        "lockouts": record.lockouts,
        "allocated": record.allocated,
        "professions": record.professions,
        "reputation": record.reputation,
        "friends": record.friends,
    }
    if record.auth_salt and record.auth_hash:
        casefile["auth"] = {"salt": record.auth_salt, "hash": record.auth_hash}
    return casefile


def load_character(name: str, store: CharacterStore | None = None) -> dict[str, Any] | None:
    record = (store or _default_store()).find(name)
    return _record_to_casefile(record) if record is not None else None


def put_record(name: str, casefile: dict[str, Any], store: CharacterStore | None = None) -> None:
    """Write one full casefile through the single storage door (auth columns included)."""
    from kernel.world.world import START_ROOM

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
        guild=casefile.get("guild", ""),
        guild_rank=casefile.get("guild_rank", ""),
        equipped_gear=casefile.get("equipped_gear", ""),
        coins=int(casefile.get("coins", 0)),
        quest_state=casefile.get("quest_state", ""),
        lockouts=casefile.get("lockouts", ""),
        allocated=casefile.get("allocated", ""),
        professions=casefile.get("professions", ""),
        reputation=casefile.get("reputation", ""),
        friends=casefile.get("friends", ""),
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
    from kernel.world.quest import save_state

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
        guild=session.guild,
        guild_rank=session.guild_rank,
        equipped_gear=_serialize_gear(session),
        coins=session.coins,
        quest_state=save_state(session.player_id),
        lockouts=lockouts_mod.serialize(session.lockouts),
        allocated=allocate.serialize(session),
        professions=professions.serialize(session),
        reputation=reputation.serialize(session),
        friends=friends_mod.serialize(session),
    )
    (store or _default_store()).upsert_gameplay(record)
    # Persist per-job progress AFTER the character row exists (the foreign key needs it).
    if session.job_progress:
        save_job_progress(session.player_id, session.job_progress.values())
    # Persist the loose bag (Keystone A): everything carried but not worn, so it survives logout.
    from kernel.world.loose_store import save as save_loose

    save_loose(session.player_id, _snapshot_loose(session))


def save_all(store: CharacterStore | None = None) -> int:
    """Persist EVERY named live hero at once (the autosave sweep and the save-on-shutdown drain) and
    return how many were saved. So a crash or a restart loses at most the interval since the last
    sweep, not a whole session of progress.

    Lock-agnostic on purpose: the caller holds the tick lock (or is the shutdown path) so no session
    is mutating mid-save. Iterates a snapshot of the roster, so a disconnect pruning SESSIONS during
    the loop never trips it."""
    from kernel.world.session import SESSIONS

    saved = 0
    for session in list(SESSIONS.values()):
        if session.named:
            save_character(session, store)
            saved += 1
    return saved


def restore_character(session: Session, casefile: dict[str, Any]) -> None:
    """Rebuild the full sheet from minimal state. Resources return full:
    logging back in is a night's rest."""
    session.named = True
    session.rank = str(casefile.get("rank", "player"))
    session.account = str(casefile.get("account", ""))
    session.order = str(casefile.get("order", ""))
    session.guild = str(casefile.get("guild", ""))
    session.guild_rank = str(casefile.get("guild_rank", ""))
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
    # Drop any items still tagged to this carrier (a same-process reconnect leaves orphans), so the
    # re-clones below never stack on top of a previous session's instances and double the bag.
    _clear_carrier(session.player_id)
    # ...then re-clone and re-equip THIS hero's own persisted gear (folds back into their stats).
    _restore_gear(session, str(casefile.get("equipped_gear", "")))
    # ...and re-clone their loose bag (Keystone A), so everything carried but not worn is back too.
    from kernel.world.items import carrier as _carrier
    from kernel.world.loose_store import load as load_loose

    for snap in load_loose(session.player_id):
        reclone_item(snap, _carrier(session.player_id))
    # ...and seed their quest arc back to where they left it, so a story-in-progress survives.
    from kernel.world.quest import restore_state

    restore_state(session.player_id, str(casefile.get("quest_state", "")))
    # ...and restore the daily lockout ledger, so the once-a-day boss bonus cap survives logout.
    session.lockouts = lockouts_mod.deserialize(str(casefile.get("lockouts", "")))
    # Load allocated attribute points BEFORE building stats, so bind_calling folds them into the
    # StatBlock (and the HP/MP recompute below includes the allocated stamina/magic).
    allocate.restore(session, str(casefile.get("allocated", "")))
    # Rebuild the maker's trades; level recomputes from practice (derive-don't-store).
    professions.restore(session, str(casefile.get("professions", "")))
    # Rebuild standing with the Orders; the tier recomputes from the number (derive-don't-store).
    reputation.restore(session, str(casefile.get("reputation", "")))
    # Rebuild this hero's personal friends list.
    friends_mod.restore(session, str(casefile.get("friends", "")))
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
