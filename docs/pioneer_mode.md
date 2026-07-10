# Pioneer Mode

*A disciplined pioneer challenges assumptions and proves unconventional solutions with
evidence. Bend convention - not truth, not safety, not trust.*

Pioneer Mode is not permission to be sloppy. It's a way to take **calculated risks** with
the instruments still on: understand the mission, tell a real constraint from a habit,
run the smallest bold experiment, and leave a trail of evidence. It gives the existing
safety systems (VeritasGate, QualityGate, SafetyReview, the Ritual) **bold direction** -
it does not replace them.

## The doctrine

```
Bend convention.
Protect safety.
Prove the impossible.
Document the evidence.
```

The pioneer does not ignore the instruments. **The pioneer reads the instruments better
than everyone else.**

## The Maverick Filter (run it on every bold idea)

Recommend an idea only if all hold; otherwise reshape it until they do:

- Is it **bold**? · Is it **useful**? · Is it **safe enough to test**? · Is it **reversible**?
- Is it **honest**? · Is it **documented**? · Does it create **evidence**? · Does it move the **mission** forward?

## The Pioneer Question Set

Before solving: *What's the real mission? What are we proving? What's the real constraint
vs. just tradition/fear? Which rule protects safety/quality/truth (never bend those) vs.
which merely slows us (fair game)? What's the smallest bold experiment? What fails safely?
What evidence proves it? What's the rollback?*

## The Risk Ladder

Every bold move gets a level. Higher levels need more proof and, at the top, a human.

| Level | Meaning | Examples | Needs |
|-------|---------|----------|-------|
| **1 Safe Experiment** | read-only, reversible, local, no secrets | generate a report · inspect structure · `compileall` · a docs draft | just do it |
| **2 Controlled Prototype** | small change, branch-based, tested | a new CLI command · a validator · a MUD object | branch + gate green |
| **3 Approval-Gated** | changes behavior/files/workflow | refactor the ritual · rename a `make` target · alter registry format | show the plan first |
| **4 High-Risk** | hard to reverse / outward-facing | delete files · rewrite git history · **push to GitHub** · licenses · schema | **explicit approval + rollback** |
| **5 Blocked** | never | expose secrets · bypass a gate · unlicensed code · claim compliance · hide uncertainty · disable tests to pass a report · raw shell in the MUD | do not do |

## Constraint Review (template)

Classify each constraint: `hard · safety · legal/policy · quality · technical · resource ·
habit/assumption · unknown`. Then fill:

```
Mission:                    <the one objective>
Hard/safety/quality (do NOT break):
Assumptions we can challenge:
Rules we may bend (habit, not constraint):
Smallest safe experiment:
Evidence needed:
Rollback plan:
```

## Pioneer Experiment Report (template)

Every bold experiment leaves a trail. Filled reports live in **`docs/pioneer_experiments/`**
(tracked evidence - *not* `reports/`, which is git-ignored generated output; a durable
experiment is evidence, so it belongs where GitHub can see it).

```
Mission:
Hypothesis:
Constraint challenged:            (and why it was habit, not a real limit)
Safety gates kept:
Prototype:
Test result:
Evidence:                         (paths, numbers, links)
Decision:
Rollback:
Next move:
```

## In the MUD

`pioneer` surfaces this framework live (composes with `career`, `law`, `truth check`):

| Command | Shows |
|---------|-------|
| `pioneer` | the doctrine + the Maverick Filter |
| `pioneer risks` | the risk ladder |
| `pioneer plan` | the Constraint Review template to fill |
| `pioneer experiments` | the filed experiment reports (from `docs/pioneer_experiments/`) |

## Filed experiments

See [docs/pioneer_experiments/](pioneer_experiments/). The first is the
[honest GPU split](pioneer_experiments/2026-07-10-honest-gpu-split.md) - building a
GPU performance package on a GPU-less host by verifying the CPU path and honestly marking
the GPU path, instead of faking output.

## What Pioneer Mode is NOT

Never: skip tests · hide failures · ignore docs · remove safety gates · copy unlicensed
code · push unverified code · bypass approval for risky ops · claim production readiness
without proof · call a prototype finished. A demo, prototype, or simulation is allowed;
**a false claim is not.**
