# ADR-0002: Derive, don't store (inherited from the mk1 kernel)

**Status:** accepted

**Decision:** Persist the minimum canonical facts (job, level, xp, location, rank,
account). Recompute stats and resources on restore from job templates and the
locked progression formulas. Resources are immutable-with-replacement: transitions
return new instances.

**Consequences:** save files stay tiny and honest; recomputable data cannot drift
from its source of truth; `test_restored_hero_matches_a_live_grown_one` pins
restore-math equal to play-math.
