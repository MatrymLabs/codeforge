"""CARD: abilities -- a job's usable combat moves: strikes that scale on a stat, and self-heals.

This is the batch the Job card promised ("combat wiring is a later batch"). An ability is data
(parts.world.seed.Ability, loaded from abilities.yaml): a `strike` deals `power + stat // 3` damage
to a target, a `heal` restores the wielder's HP, and each costs MP. Which jobs may wield an ability
lives in the ability's `jobs` list, so a Vanguard and a Scholar fight differently without a line of
hardcoding. `use <ability> [on <target>]` fires one; `skills` lists what your calling can wield.

Strikes reuse combat.land_hit, so an ability shares the exact defeat/award/loot/quest machinery the
basic attack uses -- a foe felled by a skill still drops loot and advances a quest.
"""

from __future__ import annotations

from parts.world import combat
from parts.world.events import announce
from parts.world.npcs import NPCS, trace_npc
from parts.world.seed import SEED_DIR, Ability, load_abilities
from parts.world.session import Session, display_name, sentence_case

# The world is data: a seed's abilities live in its own abilities.yaml (empty if it ships none).
ABILITIES: dict[str, Ability] = load_abilities(SEED_DIR / "abilities.yaml")


def abilities_for(job: str) -> list[tuple[str, Ability]]:
    """The (label, ability) pairs a job may wield, sorted by display name (empty for no job)."""
    if not job:
        return []
    pairs = [(label, a) for label, a in ABILITIES.items() if job in a["jobs"]]
    return sorted(pairs, key=lambda pair: pair[1]["name"].lower())


def _wielded_jobs(session: Session) -> set[str]:
    """The jobs whose kit a character can wield NOW: the primary AND the sworn subjob (FFXI-style
    -- your subjob lends its moves). Empty labels are dropped, so a subjob-less seat is fine."""
    return {job for job in (session.job, session.secondary_job) if job}


def abilities_for_session(session: Session) -> list[tuple[str, Ability]]:
    """Every ability a character may wield: their primary job's AND their subjob's, deduped and
    sorted. This is the switchable kit -- change your subjob and a different moveset opens up."""
    jobs = _wielded_jobs(session)
    pairs = [(label, a) for label, a in ABILITIES.items() if jobs & set(a["jobs"])]
    return sorted(pairs, key=lambda pair: pair[1]["name"].lower())


def _magnitude(session: Session, ability: Ability) -> int:
    """An ability's effect size: its flat power plus a third of the attribute it scales on."""
    scaled = (
        session.stats.get(ability["scales"]).base if (session.stats and ability["scales"]) else 0
    )
    return ability["power"] + scaled // 3


def _resolve(name: str) -> tuple[str, Ability] | None:
    """Find an ability by its label or its display name (case-insensitive), or None."""
    key = name.strip().lower().replace(" ", "_")
    for label, ability in ABILITIES.items():
        if label == key or ability["name"].lower() == name.strip().lower():
            return (label, ability)
    return None


def render_abilities(session: Session) -> str:
    """List the abilities the player's calling can wield (the `skills` verb)."""
    if session.stats is None:
        return "You have no calling yet. Type JOBS before you learn skills."
    pairs = abilities_for_session(session)
    if not pairs:
        return "Your calling has no abilities yet."
    subjob_only = {label for label, _ in pairs} - {label for label, _ in abilities_for(session.job)}
    lines = ["Abilities:"]
    for label, a in pairs:
        target = "self" if a["kind"] == "heal" else "a target"
        scale = f" +{a['scales']}/3" if a["scales"] else ""
        via = "  (subjob)" if label in subjob_only else ""
        lines.append(
            f"  {a['name']} ({a['kind']} {target}, {a['mp_cost']} MP): {a['power']}{scale}{via}"
        )
    lines.append("Use one with:  use <ability> [on <target>]")
    return "\n".join(lines)


def use_ability(session: Session, arg: str) -> str:
    """Channel one ability: `use <ability> [on <target>]`. Fails loud, spends MP only on success."""
    if session.stats is None:
        return "You have no calling yet. Type JOBS before you channel a skill."
    name, _, target_word = arg.partition(" on ")
    found = _resolve(name)
    if found is None:
        return f"You know no ability called '{name.strip()}'. Type SKILLS to see yours."
    label, ability = found
    if not _wielded_jobs(session) & set(ability["jobs"]):
        return f"Your calling cannot wield {ability['name']}. Type SKILLS to see yours."
    mp = session.resources["mp"]
    if mp.current < ability["mp_cost"]:
        return f"Not enough MP for {ability['name']} ({mp.current}/{ability['mp_cost']})."

    who = display_name(session.player_id)
    move = ability["name"]
    if ability["kind"] == "heal":
        session.resources["mp"] = mp.damage(ability["mp_cost"])
        amount = _magnitude(session, ability)
        session.resources["hp"] = session.resources["hp"].heal(amount)
        healed = session.resources["hp"]
        announce(session.location, f"{who} channels {move}.", exclude=session.player_id)
        return f"You channel {move} and recover {amount} HP. ({healed.current}/{healed.maximum})"

    # a strike needs a target
    nid = trace_npc(target_word.strip(), session.location) if target_word.strip() else None
    if nid is None:
        return f"Use {move} on whom? Try: use {move} on <target>"
    npc = NPCS[nid]
    if npc["hp"] <= 0:
        return f"{sentence_case(npc['name'])} is not something you can fight."
    session.resources["mp"] = mp.damage(ability["mp_cost"])
    dmg = _magnitude(session, ability)
    announce(
        session.location,
        f"{who} unleashes {move} on {npc['name']} for {dmg}.",
        exclude=session.player_id,
    )
    defeated, tail = combat.land_hit(session, npc, nid, dmg)
    if not defeated:
        bar = f"{npc['hp_now']}/{npc['hp']}"
        return f"You unleash {move} on {npc['name']} for {dmg}. ({bar})"
    return f"You unleash {move} on {npc['name']}; it collapses -- then reassembles itself.\n{tail}"
