# DISPATCH CX-010

```yaml
packet_id:            CX-010
title:                One quest completion may not advance a character more than one level
stream:               codeforge
owner:                Codex
reviewer:             Claude Code (re-runs every command independently)
merges:               founder
size:                 small
flight:               M2 Engine Real
queue_position:       after CX-009 and WO-S2.

goal: >
  Close codeforge #910. A new character reaches level 7 on its first move, because a zone errand
  pays against the DESTINATION zone's level band with no reference to the character's level.

  The issue names two separable causes. This order fixes ONE of them, the reward. The other,
  Veridia sharing a cardinal border with a levels 60-90 zone, is world geography and belongs to
  the founder, not to a bench. Do not touch the map.

design_decision: >
  Proposed by Claude Code, founder-approvable, stated here so it is not decided by implementation:

  NO SINGLE QUEST COMPLETION MAY ADVANCE A CHARACTER MORE THAN ONE LEVEL.

  Chosen over a zone-band table because it needs no balance data, holds for every quest kind
  (errand, bounty, delivery, cull, forage, dungeon), and is a property rather than a tuned number.
  A level-appropriate character never hits the cap, so ordinary play is unchanged. It also does not
  require regenerating any content: errand XP stays advertised as posted, and the CAP applies at
  the moment of payment.

  If the founder wants an over-levelled character to earn nothing rather than a capped amount,
  that is a different rule and a different order. Do not choose between them yourself.

named_consumers:
  - codeforge #910          the reported defect
  - the M1 spine walk       which found it, and which no leg-level test could have found

preconditions: >
  CHECK: file kernel/world/errands.py contains XP
  CHECK: file kernel/world/progression.py exists
  CHECK: file content/seeds/aethryn/canon.yaml contains Frostspire

  codeforge #918 (WO-S1) merged, so the seam work is not in flight underneath this.
  kernel/world/quest.py line 442 currently reads `award_xp(session, quest.xp)`; that call site is
  the ONLY place a quest's reward is paid, and it already holds the session, so the character's
  level is in scope without threading anything new.
  kernel/world/progression.py provides `cumulative_xp_for_level`.

verification_command: |
  # Your registered codeforge worktree. Confirm with `git worktree list`.
  cd <your registered codeforge worktree>
  export PATH="$PWD/.venv/bin:$PATH"
  git fetch origin && git rev-list --count HEAD..origin/main   # must print 0
  make check

definition_of_done: >
  A quest payment is capped so the character can gain at most one level from it; the cap is applied
  at the single award site rather than at each quest generator; the reproduction from #910 yields
  exactly one LEVEL UP line instead of six; make check green with the whole gate, not a subset.

out_of_scope: >
  The map. Veridia's north exit is world geography and the founder's call.
  Every quest GENERATOR (errands.py, bounties.py, delivery.py, cull.py, forage.py,
  dungeon_crawl.py). Fixing six generators is fixing the output six times; the award site is the
  generator of the behaviour.
  Rebalancing _XP_PER_LEVEL. That is a tuning argument, not this defect.

approval_gates: >
  Founder merges. The design decision above is his to confirm; if he rejects it, STOP rather than
  substituting your own rule.

rollback: >
  git revert. One clamp and its tests.

boundary: >
  Computed by packet_gate: 14 first-party modules imported and not changeable here.

  The reward cap is enforced at ONE place on purpose. errands.py, bounties.py, forage.py,
  dungeon_crawl.py, storylines.py and progression_awards.py each grant XP, and widening this order
  to all of them would make six edits where one belongs. The cap belongs where a grant becomes
  progression, and everything upstream keeps paying what its own design says.

  statemachine, workflow, cull, jobs, reputation, seed, session, spine are collaborators that
  neither grant nor apply progression.

amendment_1: >
    AMENDED 2026-08-12 by the Coordinator, after Codex correctly BLOCKED on it. The original
    allowlist was UNSATISFIABLE and the fault is the order's, not the implementation's.

    The clamp works: a fresh character walking the Forgeward Road now gains 75 XP and one level
    where it previously gained 12000 XP and six. But two end-to-end journey tests assert the
    UNCAPPED reward by value, and neither was in the allowlist, so the packet could not be
    completed without leaving it. Measured on work/cx010 with the full suite, not the first
    failure: exactly two fail, 5208 pass.

      tests/test_journey_aethryn.py::test_the_real_forgeward_road_walks_to_the_voidscar
      tests/test_journey_spine.py::test_the_forgeward_road_walks_from_the_valley_to_the_endgame

    Both are now WRONG, not broken. They pin the instrument, `assert f"You gain {spec['reward_xp']}
    XP" in out`, when what the journey actually cares about is the invariant: the character reached
    the endgame and gained a level. Rewrite them to assert ONE LEVEL WAS GAINED rather than a
    hardcoded XP figure. Do not delete either test, and do not weaken the walk itself.

    Why the order got this wrong, recorded so the next one does not: the allowlist was scoped from
    the MODULE being changed rather than from the set of artifacts that assert on its behaviour.
    `make packets` cannot catch that; it has no way to know which tests read the value. The check
    that would have caught it is a grep for the value before the allowlist is fixed.

founder_question: >
    Raised, not decided, because it is a product ruling. The clamp awards exactly enough to reach
    the next level and DISCARDS the remainder: a 12000 XP campaign reward paid to a level-1
    character yields 75 XP and 11,925 evaporate. That is the honest reading of "no single quest may
    advance more than one level", and it only bites in these speedrun tests, since a character
    reaching the endgame in real play arrives around level 50 and one level there is a large award.

    Flagging it because the alternative, banking the excess toward the following level, is a
    different game. Do not implement either alternative in this packet; the clamp as written closes
    #910. If Josh rules for banking, that is its own order.

file_allowlist:
  - kernel/world/quest.py                  # the clamp, at the single award site
  - tests/test_quest.py                    # its twin
  - tests/test_journey_aethryn.py          # AMENDED: assert one level gained, not an XP literal
  - tests/test_journey_spine.py            # AMENDED: same
  - handoff/CX-010/RETURN.md               # NEW, explicitly authorised

contract_tests:       tests/test_quest.py
contract_test_policy: |
  ASSERTION-LOCKED. Add these to the existing file. You may ADD; you may not weaken or remove.

return_artifact:      handoff/CX-010/RETURN.md
return_authorisation: |
  EXPLICITLY AUTHORISED. Required. Record `git rev-list --count HEAD..origin/main` WITH its output,
  and record what the gate COLLECTED, not only what passed. Both are live findings from REDTEAM-01.

store_search_result: |
  SEARCH BOTH TIERS and log both, per ADR-0005. Search "clamp", "cap", "rate limit", "progression".
  A one-tier search that finds nothing is an incomplete search.

parts_to_consume: |
  UNKNOWN until you search. Likely none: this is a domain rule, not a capability.

watch_for: |
  The cap must be computed from the character's CURRENT level at the moment of payment, not from a
  value captured when the quest was accepted. A character who levels between accepting and
  completing must be judged on what it is now.
```

## The measurement

`CMD` `kernel/world/errands.py:40`

```python
reward = level * _XP_PER_LEVEL  # `level` is the DESTINATION zone's, never the character's
```

`CMD` `kernel/world/quest.py:442`

```python
if effect == "award_xp" and session.stats is not None:
    from kernel.world.progression_awards import award_xp

    return "\n" + award_xp(session, quest.xp)
```

One award site, session in hand. That is why the fix belongs here and not in six generators.

## Invariant

**No single quest completion may advance a character by more than one level, whatever the quest
advertises and wherever it was earned.**

## The contract tests, verbatim

Append to `tests/test_quest.py`.

```python
def test_one_quest_cannot_advance_a_character_more_than_one_level() -> None:
    """codeforge #910: a level 1 character reached level 7 on its first move.

    The errand paid against the destination zone's band (levels 60-90) with no reference to the
    character. The property is deliberately about LEVELS rather than about XP numbers, because a
    test pinned to a number pins the instrument instead of the invariant.
    """
    session = _fresh_session(level=1)
    before = session.stats.level
    _complete_quest(session, reward_xp=100_000)
    assert session.stats.level <= before + 1, (
        f"one quest advanced the character from {before} to {session.stats.level}"
    )


def test_a_level_appropriate_reward_is_paid_in_full() -> None:
    """Calibration. If the clamp bit during ordinary play it would be a nerf, not a fix."""
    session = _fresh_session(level=10)
    modest = 5
    before_xp = session.stats.xp
    _complete_quest(session, reward_xp=modest)
    assert session.stats.xp == before_xp + modest


def test_the_cap_reads_the_characters_level_at_payment_not_at_acceptance() -> None:
    """A character who levels between accepting and completing is judged on what it is now."""
    session = _fresh_session(level=1)
    quest = _accept_quest(session, reward_xp=100_000)
    _set_level(session, 20)
    _finish(session, quest)
    assert session.stats.level <= 21
```

`_fresh_session`, `_complete_quest`, `_accept_quest`, `_set_level` and `_finish` are helpers you
write to match the existing file's conventions. Do not change the assertions.

## Definition of done

```bash
cd <your registered codeforge worktree>
export PATH="$PWD/.venv/bin:$PATH"
make check
```

Plus the #910 reproduction run live, with its output in the RETURN: a new character, `north`, and
exactly one LEVEL UP line where there were six.
