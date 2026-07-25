# The ADDIE Loop

CodeForge should not move in a straight line. It should learn in a loop.

ADDIE is a lightweight systems-engineering self-check CodeForge applies whenever it plans, builds,
changes, tests, or evaluates anything: a feature, subsystem, workflow, client capability, Hardware
Store part, Blueprint, Seed, automation, or fleet integration. It is a **circular operating method**,
not a lesson authoring tool and not a new authority.

## The cycle

**ANALYZE** - What problem are we solving? What does the current vision require? What already exists?
What gaps, risks, constraints, dependencies, and assumptions are present? What evidence defines
success?

**DESIGN** - What is the smallest coherent solution? Where does it belong in the architecture? What
interfaces, boundaries, tests, security controls, documentation, and rollback are required? How does
it support CodeForge and the fleet without unnecessary complexity?

**DEVELOP** - Build the approved solution in a controlled, modular, testable way. Reuse existing
Hardware Store parts before creating new ones. Keep Python as the native engineering spine. Preserve
working behavior unless change is intentional and approved.

**IMPLEMENT** - Integrate it into the real CodeForge workflow: the affected systems, commands, Ritual
checks, Blueprints, Hardware Cards, documentation, and fleet consumers. Verify that installation,
startup, operation, shutdown, migration, and rollback still work.

**EVALUATE** - Compare the result against the original problem, Blueprint, tests, metrics, security
requirements, documentation, user experience, and the vision. Identify defects, drift, duplication,
missing evidence, and unintended consequences. Decide whether to keep, revise, split, merge, version,
defer, or remove the result.

Then loop back to **ANALYZE**:

```
Analyze -> Design -> Develop -> Implement -> Evaluate -> Reanalyze
```

## Lightweight by rule

Do not generate a long ADDIE report for every small edit. For **minor** work, run the check silently
and surface only meaningful findings. For **major** work, file a brief ADDIE Self-Check:

- **Analyze:** what problem and gap were identified
- **Design:** what solution and boundaries were chosen
- **Develop:** what was built
- **Implement:** where it was integrated
- **Evaluate:** what evidence shows whether it worked
- **Next cycle:** what should be analyzed next

## The four failure modes it prevents

ADDIE exists to stop CodeForge from:

- **building without understanding** (no ANALYZE),
- **designing without evidence** (no DESIGN),
- **implementing without integration** (no IMPLEMENT),
- **declaring success without evaluation** (no EVALUATE).

`parts/addie.py` encodes this: a major cycle that skips any phase, or leaves the loop open (no next
cycle), is refused by `gaps()`. Major cycles are filed in `addie_ledger.toml`; `make addie` (and the
test twin on `make check`) fails loud if a filed cycle did not close its loop. The `addie` verb
(`addie status`) surfaces the same audit in the world, the way `arc` surfaces the readiness verdict.

## It composes; it does not override

ADDIE adds no new authority and overrides no established CodeForge control. It is the loop those
controls run inside:

- **Blueprints** - a Blueprint is the DESIGN phase written down; the ADDIE Self-Check is its
  loop-shaped companion (analyze -> ... -> evaluate -> reanalyze).
- **ARC / AURA** - ARC composes the readiness verdict; ADDIE's EVALUATE phase reads that verdict
  rather than replacing it. ARC also reads the ADDIE ledger back as its **improvement** dimension:
  READY when every filed major cycle closed its loop, WATCHLIST when one skipped a phase, MISSING
  when no ledger is filed (never a faked pass). So a cycle that declared success without evaluation
  shows up on the readiness roll-up.
- **Ritual** - the RepoIntegrityRitual is EVALUATE run against the whole repo; ADDIE points to it,
  it does not duplicate it.
- **Hardware Store + Hardware Cards** - DEVELOP reuses existing parts first; a new part earns its
  Card, and its Card is its own small ADDIE record.
- **testing / security / documentation** - these are the evidence EVALUATE reads; ADDIE never lowers
  their bar, it requires that they were consulted before success is declared.
- **fleet governance** - IMPLEMENT names the fleet consumers a change touches, so a repo cannot
  declare done while a sibling repo silently breaks.

## Using it in code

```python
from parts.addie import self_check, gaps

check = self_check(
    "the thing under review",
    analyze="the gap",
    design="the smallest solution",
    develop="what was built",
    implement="where it integrated",
    evaluate="the evidence it worked",
    next_cycle="what to analyze next",
)
assert gaps(check) == []  # refuses an unlooped cycle
```

Analyze the need. Design the response. Develop the capability. Implement it in the real system.
Evaluate it against the vision and the evidence. Then begin the next, better cycle.
