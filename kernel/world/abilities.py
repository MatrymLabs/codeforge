"""CARD: abilities -- a job's usable combat moves: strikes, drains, brands, control, and heals.

This is the batch the Job card promised ("combat wiring is a later batch"). An ability is data
(kernel.world.seed.Ability, loaded from abilities.yaml): a `strike` deals `power + stat // 3` damage
to a target, a `drain` strikes AND siphons half the damage back as HP, a `brand` lays a burn DoT, a
`daze`/`weaken` control or soften a foe, and a `heal` restores HP -- the wielder's, or an ALLY's in
the same room (the trinity seam: a healer can mend a party-mate) -- and each costs MP. Which jobs
may wield an ability lives in the ability's `jobs` list, so a Vanguard and a Scholar fight without a
line of hardcoding. `use <ability> [on <target>]` fires one; `skills` lists what your calling has.

Strikes reuse combat.land_hit, so an ability shares the exact defeat/award/loot/quest machinery the
basic attack uses -- a foe felled by a skill still drops loot and advances a quest.

CADENCE: an ability may declare a `cooldown` (combat beats). After a successful channel it is locked
out until the combat clock thaws it -- and a landed strike (the basic `attack`, or a strike ability)
advances that clock (kernel.world.combat_clock). So a fight is no longer "spam strongest button":
you open with a cooldown move, weave basic attacks as filler, and rotate skills back as they thaw.
A move with no cooldown stays MP-limited only.
"""

from __future__ import annotations

from kernel.world import combat, mortality, threat
from kernel.world.events import announce, announce_to
from kernel.world.npcs import NPCS, trace_npc
from kernel.world.seed import SEED_DIR, Ability, Npc, load_abilities
from kernel.world.session import SESSIONS, Session, display_name, sentence_case

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
        target = "self or ally" if a["kind"] in ("heal", "cleanse", "buff", "regen") else "a target"
        scale = f" +{a['scales']}/3" if a["scales"] else ""
        via = "  (subjob)" if label in subjob_only else ""
        cd = a.get("cooldown", 0)
        recovering = session.cooldowns.get(label, 0)
        if recovering > 0:  # live state: how many beats until it can be channelled again
            cadence = f", recovering {recovering}b"
        elif cd:
            cadence = f", {cd}b cooldown"
        else:
            cadence = ""
        lines.append(
            f"  {a['name']} ({a['kind']} {target}, {a['mp_cost']} MP{cadence}):"
            f" {a['power']}{scale}{via}"
        )
    lines.append("Use one with:  use <ability> [on <target>]")
    return "\n".join(lines)


def use_ability(session: Session, arg: str) -> str:
    """Channel one ability: `use <ability> [on <target>]`. Fails loud, spends MP only on success."""
    if session.stats is None:
        return "You have no calling yet. Type JOBS before you channel a skill."
    from kernel.world.afflictions import is_dazed

    if is_dazed(session):
        return "You are dazed and cannot channel a skill -- it will pass."
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
    # The cadence gate: a move on cooldown is refused until the combat clock thaws it (a landed
    # strike advances the clock - kernel.world.combat_clock). This is what turns "spam the strongest
    # button" into a rotation. A move with no cooldown is never here.
    ready = session.cooldowns.get(label, 0)
    if ready > 0:
        return (
            f"{ability['name']} is still recovering ({ready} more beat{'s' if ready != 1 else ''})."
        )

    who = display_name(session.player_id)
    move = ability["name"]
    if ability["kind"] == "heal":
        return _channel_heal(session, ability, label, target_word.strip(), who, move)
    if ability["kind"] == "cleanse":
        return _channel_cleanse(session, ability, label, target_word.strip(), who, move)
    if ability["kind"] == "regen":
        return _channel_regen(session, ability, label, target_word.strip(), who, move)
    if ability["kind"] == "buff":
        return _channel_buff(session, ability, label, target_word.strip(), who, move)

    # a strike, a drain, a brand, or a taunt needs a target
    nid = trace_npc(target_word.strip(), session.location) if target_word.strip() else None
    if nid is None:
        return f"Use {move} on whom? Try: use {move} on <target>"
    npc = NPCS[nid]
    if npc["hp"] <= 0:
        return f"{sentence_case(npc['name'])} is not something you can fight."
    if ability["kind"] == "taunt":
        return _channel_taunt(session, ability, label, npc, nid, who, move)
    session.resources["mp"] = mp.damage(ability["mp_cost"])
    # The offense resolves (a landed strike advances the clock); the cooldown is armed AFTER, so it
    # is set to its full duration and not thawed by this same action's own clock advance.
    result = _channel_offense(session, ability, npc, nid, who, move)
    _arm_cooldown(session, label, ability)
    return result


def _trace_ally(target_word: str, session: Session) -> Session | None:
    """Resolve who a heal should mend: an empty or self-referring target is the wielder; otherwise a
    living player in the same room, matched by handle or display name (the trinity seam). A cross-
    process ally (a party-mate on another gateway) is not a local session, so it is out of reach
    until shared authoritative session state exists -- room-local healing, honestly bounded."""
    key = target_word.strip().lower()
    mine = display_name(session.player_id).lower()
    if key in ("", "me", "self", "myself", session.player_id.lower(), mine):
        return session
    for pid, other in list(SESSIONS.items()):
        if other is session or other.location != session.location:
            continue
        if key in (pid.lower(), display_name(pid).lower()):
            return other
    return None


def _channel_heal(
    session: Session, ability: Ability, label: str, target_word: str, who: str, move: str
) -> str:
    """Mend the wielder or an ally in the room. Spends MP and arms the cooldown only on a real
    target; a named ally who is not present fails loud so the MP is never burned into the void."""
    ally = _trace_ally(target_word, session)
    if ally is None:
        return f"There is no ally called '{target_word}' here to mend."
    session.resources["mp"] = session.resources["mp"].damage(ability["mp_cost"])
    amount = _magnitude(session, ability)
    ally.resources["hp"] = ally.resources["hp"].heal(amount)
    healed = ally.resources["hp"]
    _arm_cooldown(session, label, ability)
    _heal_threat(session, amount)  # mending draws aggro: every engaged foe now eyes the healer
    if ally is session:
        announce(session.location, f"{who} channels {move}.", exclude=session.player_id)
        return f"You channel {move} and recover {amount} HP. ({healed.current}/{healed.maximum})"
    ally_name = display_name(ally.player_id)
    announce(session.location, f"{who} channels {move} on {ally_name}.", exclude=session.player_id)
    announce_to(
        [ally.player_id],
        f"{who} channels {move} on you; you recover {amount} HP. "
        f"({healed.current}/{healed.maximum})",
        exclude=session.player_id,
    )
    return (
        f"You channel {move} on {ally_name}, mending {amount} HP. "
        f"({healed.current}/{healed.maximum})"
    )


def _channel_regen(
    session: Session, ability: Ability, label: str, target_word: str, who: str, move: str
) -> str:
    """Weave a heal-over-time on the wielder or an ally: it mends a share each beat for a few beats
    (the friendly mirror of a `brand` burn). Spends MP + arms the cooldown only on a real target; a
    named ally who is not present fails loud, so the MP is never burned into the void."""
    from kernel.world import afflictions

    ally = _trace_ally(target_word, session)
    if ally is None:
        return f"There is no ally called '{target_word}' here to bless."
    session.resources["mp"] = session.resources["mp"].damage(ability["mp_cost"])
    per_beat = _magnitude(session, ability)
    ticks = afflictions.DOT_TICKS
    afflictions.apply_regen(ally, move.lower(), per_beat, ticks)
    _arm_cooldown(session, label, ability)
    _heal_threat(session, per_beat)  # weaving a mend draws aggro, like a heal
    if ally is session:
        announce(session.location, f"{who} weaves {move}.", exclude=session.player_id)
        return f"You weave {move}: it will mend {per_beat} HP a beat for {ticks} beats."
    ally_name = display_name(ally.player_id)
    announce(session.location, f"{who} weaves {move} on {ally_name}.", exclude=session.player_id)
    return f"You weave {move} on {ally_name}: it mends {per_beat} HP a beat for {ticks} beats."


def _channel_cleanse(
    session: Session, ability: Ability, label: str, target_word: str, who: str, move: str
) -> str:
    """Purge an ally's afflictions (the support's counter to a boss's venom and stuns). Costs MP and
    arms the cooldown ONLY when there was something to cleanse -- a wasted cleanse on a clean hero
    never burns the MP. Reuses _trace_ally, so `on me` / `on <ally>` resolve like a heal."""
    from kernel.world import afflictions

    ally = _trace_ally(target_word, session)
    if ally is None:
        return f"There is no ally called '{target_word}' here to cleanse."
    them = "you" if ally is session else display_name(ally.player_id)
    if not (ally.afflictions or ally.dazed):
        return f"Nothing ails {them}."  # a clean target: no effect, no MP spent
    purged = afflictions.cleanse(ally)
    session.resources["mp"] = session.resources["mp"].damage(ability["mp_cost"])
    _arm_cooldown(session, label, ability)
    cleared = ", ".join(purged)
    if ally is session:
        announce(session.location, f"{who} channels {move}.", exclude=session.player_id)
        return f"You channel {move} and shake off {cleared}."
    ally_name = display_name(ally.player_id)
    announce(session.location, f"{who} channels {move} on {ally_name}.", exclude=session.player_id)
    announce_to(
        [ally.player_id],
        f"{who} channels {move} on you; {cleared} is purged.",
        exclude=session.player_id,
    )
    return f"You channel {move} on {ally_name}, purging {cleared}."


def _channel_buff(
    session: Session, ability: Ability, label: str, target_word: str, who: str, move: str
) -> str:
    """Empower an ally's blows for a spell: set the `empowered` combat status, which combat.attack
    reads for a heavier strike, ticking down as they fight (like the Engineer's own scan). Reuses
    _trace_ally, so `on me` / `on <ally>` resolve like a heal. The ability's `power` is the duration
    (combat actions the buff lasts)."""
    ally = _trace_ally(target_word, session)
    if ally is None:
        return f"There is no ally called '{target_word}' here to empower."
    session.resources["mp"] = session.resources["mp"].damage(ability["mp_cost"])
    ally.statuses["empowered"] = max(ally.statuses.get("empowered", 0), ability["power"])
    _arm_cooldown(session, label, ability)
    if ally is session:
        announce(session.location, f"{who} channels {move}.", exclude=session.player_id)
        return f"You channel {move}; your blows are empowered for {ability['power']}."
    ally_name = display_name(ally.player_id)
    announce(session.location, f"{who} channels {move} on {ally_name}.", exclude=session.player_id)
    announce_to(
        [ally.player_id],
        f"{who} channels {move} on you; your blows are empowered for {ability['power']}.",
        exclude=session.player_id,
    )
    return f"You channel {move} on {ally_name}; their blows are empowered for {ability['power']}."


def _heal_threat(session: Session, amount: int) -> None:
    """A heal is loud: it generates threat on every aggressive foe in the room, so a healer climbs
    the aggro table and a tank must peel them off. Half the mended amount, the MMO convention."""
    from kernel.world.npcs import npcs_in

    gain = max(1, amount // 2)
    for nid in npcs_in(session.location):
        if NPCS[nid].get("aggressive"):
            threat.add(nid, session.player_id, gain)


def _channel_taunt(
    session: Session, ability: Ability, label: str, npc: Npc, nid: str, who: str, move: str
) -> str:
    """Force a foe's aggro onto the wielder: spike their threat one above the room's current top, so
    the foe turns from the healer or the glass cannon to the tank. Spends MP, arms the cooldown."""
    present_ids = [
        pid
        for pid, other in list(SESSIONS.items())
        if other.location == session.location and other.stats is not None
    ]
    session.resources["mp"] = session.resources["mp"].damage(ability["mp_cost"])
    threat.taunt(nid, session.player_id, present_ids)
    _arm_cooldown(session, label, ability)
    foe = sentence_case(npc["name"])
    announce(
        session.location,
        f"{who} channels {move}, seizing {npc['name']}'s attention.",
        exclude=session.player_id,
    )
    return f"You channel {move} on {foe}; its fury turns to you."


def _arm_cooldown(session: Session, label: str, ability: Ability) -> None:
    """Start a used ability's cooldown, if it has one. Called only on a successful channel, and only
    AFTER the effect (so a strike's own clock advance never thaws the cooldown it just set)."""
    cooldown = ability.get("cooldown", 0)
    if cooldown > 0:
        session.cooldowns[label] = cooldown


def _channel_offense(
    session: Session, ability: Ability, npc: Npc, nid: str, who: str, move: str
) -> str:
    """Resolve a target-facing ability (daze / weaken / brand / drain / strike) and return its line.
    MP is already spent by the caller; this only applies the effect."""
    element = ability.get("element")  # a typed move is scaled by the foe's resistance to it
    if ability["kind"] == "daze":  # crowd control: the foe skips its next beats' strikes, no damage
        beats = _magnitude(session, ability)  # scales:"" -> just power = the daze duration
        combat.apply_daze(npc, beats)
        announce(
            session.location, f"{who} dazes {npc['name']} with {move}.", exclude=session.player_id
        )
        return f"You daze {npc['name']} with {move}; it reels for {beats} beats."
    if ability["kind"] == "weaken":  # debuff: soften the foe's next blows, no damage
        blows = _magnitude(session, ability)  # scales:"" -> just power = the number of blows
        combat.apply_weaken(npc, blows)
        announce(
            session.location, f"{who} weakens {npc['name']} with {move}.", exclude=session.player_id
        )
        return f"You weaken {npc['name']} with {move}; its next {blows} blows land soft."
    if ability["kind"] == "brand":  # lay a burn DoT; it saps HP on each world beat
        per_tick, note = combat.typed_hit(npc, element, _magnitude(session, ability))
        announce(
            session.location, f"{who} brands {npc['name']} with {move}.", exclude=session.player_id
        )
        if per_tick <= 0:  # the foe nullifies the element: no burn takes hold
            return f"You brand {npc['name']} with {move}, but{note.lower()}"
        combat.apply_burn(npc, per_tick)
        bar = f"{npc['hp_now']}/{npc['hp']}"
        return f"You brand {npc['name']} with {move}; it burns for {per_tick} a beat.{note} ({bar})"
    if ability["kind"] == "drain":  # lifesteal: strike the foe AND mend the wielder for a share
        dmg, note = combat.typed_hit(npc, element, _magnitude(session, ability))
        if dmg <= 0:  # the foe nullifies the element: nothing lands, so nothing is siphoned
            announce(
                session.location,
                f"{who} reaches for {npc['name']} with {move}, to no effect.",
                exclude=session.player_id,
            )
            return f"You reach for {npc['name']} with {move}, but{note.lower()}"
        defeated, tail = combat.land_hit(session, npc, nid, dmg)
        drained = max(1, dmg // 2)  # siphon half the damage back as HP (capped at your maximum)
        session.resources["hp"] = session.resources["hp"].heal(drained)
        healed = session.resources["hp"]
        announce(
            session.location,
            f"{who} drains {npc['name']} with {move} for {dmg}.",
            exclude=session.player_id,
        )
        if defeated:
            return (
                f"You drain {npc['name']} with {move}; it {mortality.defeat_clause(npc)}. "
                f"You recover {drained} HP.\n{tail}"
            )
        bar = f"{npc['hp_now']}/{npc['hp']}"
        return (
            f"You drain {npc['name']} with {move} for {dmg}; you recover {drained} HP.{note} "
            f"(foe {bar}; you {healed.current}/{healed.maximum})"
        )
    dmg, note = combat.typed_hit(npc, element, _magnitude(session, ability))
    if dmg <= 0:  # the foe nullifies the element: the blow lands nothing
        announce(
            session.location, f"{who} unleashes {move} on {npc['name']}.", exclude=session.player_id
        )
        return f"You unleash {move} on {npc['name']}, but{note.lower()}"
    announce(
        session.location,
        f"{who} unleashes {move} on {npc['name']} for {dmg}.",
        exclude=session.player_id,
    )
    defeated, tail = combat.land_hit(session, npc, nid, dmg)
    if not defeated:
        bar = f"{npc['hp_now']}/{npc['hp']}"
        return f"You unleash {move} on {npc['name']} for {dmg}.{note} ({bar})"
    return f"You unleash {move} on {npc['name']}; it {mortality.defeat_clause(npc)}.\n{tail}"
