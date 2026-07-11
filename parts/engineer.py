"""CARD: engineer -- the Engineer job's combat kit: repair, scan, cooldowns, statuses.

The Engineer's tactical actions, built on HP/MP plus cooldowns and statuses (no custom
resource yet -- that is a deferred design juncture). Everything is DETERMINISTIC: no dice, so
every number is exact and the test twin pins it. A valid combat action advances the clock
(`tick`), counting down cooldowns and statuses and dropping the expired ones. Balance is
prototype, not final.

The kit proves the four combat pillars: a skill (Field Repair), a status (Analyzed, applied
by Diagnostic Scan), a cooldown (Field Repair recovers over ticks), and a reaction (Emergency
Repair, a counter) plus a passive (Systems Thinking, which lengthens Analyzed).
"""

from __future__ import annotations

from parts.npcs import NPCS, trace_npc
from parts.session import Session

_JOB = "engineer"

# Prototype balance knobs -- tuned later, in one place.
FIELD_REPAIR_MP = 4
FIELD_REPAIR_COOLDOWN = 2  # ticks until Field Repair is ready again
ANALYZED_BASE_DURATION = 3  # ticks the Analyzed status lasts, before the inherent
SYSTEMS_THINKING_ANALYZED_BONUS = 1  # the inherent passive: +duration on Analyzed
EMERGENCY_REPAIR_COOLDOWN = 5
EMERGENCY_HP_FRACTION = 0.30  # the counter arms when HP drops to/below 30%


def tick(session: Session) -> None:
    """Advance the combat clock one step: count every cooldown and status down, drop the expired."""
    for board in (session.cooldowns, session.statuses):
        for name in list(board):
            board[name] -= 1
            if board[name] <= 0:
                del board[name]


def _wisdom(session: Session) -> int:
    assert session.stats is not None  # an Engineer always has a stat block with wisdom
    return session.stats.get("wisdom").base


def field_repair_heal(session: Session) -> int:
    """Prototype heal: a base, plus half wisdom, plus player level. Deterministic."""
    return 6 + _wisdom(session) // 2 + session.level


def analyzed_duration(session: Session) -> int:
    """How long Analyzed lasts for this actor: base plus the inherent (Systems Thinking)."""
    bonus = SYSTEMS_THINKING_ANALYZED_BONUS if session.job == _JOB else 0
    return ANALYZED_BASE_DURATION + bonus


def field_repair(session: Session) -> str:
    """Restore HP to the Engineer for MP, then enter a cooldown. Refuses loud when not ready."""
    if session.job != _JOB:
        return "Only an Engineer can run a Field Repair."
    if "field_repair" in session.cooldowns:
        return f"Field Repair is still recovering ({session.cooldowns['field_repair']} ticks)."
    mp = session.resources["mp"]
    if mp.current < FIELD_REPAIR_MP:
        return f"Not enough MP for Field Repair (need {FIELD_REPAIR_MP}, have {mp.current})."
    tick(session)  # a valid action advances the clock (before the new cooldown is set)
    heal = field_repair_heal(session)
    session.resources["hp"] = session.resources["hp"].heal(heal)
    session.resources["mp"] = mp.damage(FIELD_REPAIR_MP)
    session.cooldowns["field_repair"] = FIELD_REPAIR_COOLDOWN
    hp = session.resources["hp"]
    return f"You run a Field Repair: +{heal} HP ({hp.current}/{hp.maximum}), -{FIELD_REPAIR_MP} MP."


def diagnostic_scan(session: Session, word: str) -> str:
    """Reveal a target's condition and apply Analyzed for a limited number of ticks."""
    if session.job != _JOB:
        return "Only an Engineer can run a Diagnostic Scan."
    nid = trace_npc(word, session.location)
    if nid is None:
        return "There is no one like that here to scan."
    npc = NPCS[nid]
    if npc["hp"] <= 0:
        return f"{npc['name'].capitalize()} is inert -- nothing to analyze."
    tick(session)
    duration = analyzed_duration(session)
    session.statuses["analyzed"] = duration
    return (
        f"Diagnostic Scan on {npc['name']}: {npc['hp_now']}/{npc['hp']} HP. "
        f"Analyzed applied ({duration} ticks)."
    )


def emergency_repair(session: Session) -> str | None:
    """The counter: when HP falls to/below the threshold, auto-repair once, then cool down.

    Pure reaction: heals a single time and arms its cooldown, so it can never fire recursively
    or twice before recovering. Returns None when it does not (or cannot) trigger.
    """
    if session.job != _JOB:
        return None
    hp = session.resources["hp"]
    if hp.current > EMERGENCY_HP_FRACTION * hp.maximum:
        return None
    if "emergency_repair" in session.cooldowns:
        return None
    heal = field_repair_heal(session)
    session.resources["hp"] = hp.heal(heal)
    session.cooldowns["emergency_repair"] = EMERGENCY_REPAIR_COOLDOWN
    return (
        f"Emergency Repair triggers: +{heal} HP ({session.resources['hp'].current}/{hp.maximum})."
    )
