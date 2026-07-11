# Fleet Scorecard: platform tooling across the ship

`forge-audit` is the ship's proof-tool: point it at a repository and it runs the quality
gates, reads the collaboration signals, and forges a machine-checked scorecard graded
against objective stage thresholds. Its **fleet mode** turns that one-repo check into a
shared surface: audit every repo on the ship in one run and roll the verdicts up into a
single fleet verdict (worst-wins, the same rule a single card uses across its dimensions).

```bash
forge-audit --fleet ../codeforge ../ai-log-triage ../federal-guidance-library \
            --stage intermediate --online --format md
```

That is platform-style tooling: one engine, many consumers (every project on the ship),
one rolled-up surface. The gates run behind mockable seams (a `Runner` for the tools, a
`RepoProbe` for the GitHub signals), so the audit is deterministic and never depends on the
network to score a repo.

## codeforge's own scorecard (intermediate stage)

The flagship graded by the same tool that grades the fleet:

### forge-audit - codeforge (intermediate stage)

| Dimension | Verdict | Evidence |
|---|---|---|
| lint | ✅ pass | clean |
| typecheck | ✅ pass | clean |
| tests | ✅ pass | green suite, coverage 95% ≥ 80% |
| security | ✅ pass | clean |
| dependencies | ✅ pass | clean |
| ci | ✅ pass | 4 CI workflow(s) |
| collaboration | ✅ pass | 30 merged PR(s) |
| **overall** | **✅ pass** | role signals: testing · security · backend · devops · collaboration |

## The rest of the fleet

The same run audits the ship's two private repos (`ai-log-triage`,
`federal-guidance-library`). Their scorecards are shared with an interviewer on request
rather than published here, to keep the private repos' internals out of the public
flagship. What the tool proves is the capability: one auditor, run across many repos,
emitting one honest surface that reports real gaps and never fakes a pass.

## How the surface stays honest

- A gate whose tool is absent reads `not_configured`, never faked as passing.
- Each repo is audited with *its own* toolchain and declared scope, so a green repo is
  never graded red for a config it never ran (the false-correspondence the tool exists to
  catch).
- Every verdict quotes its evidence; the fleet verdict is the worst repo's verdict, so one
  weak repo cannot hide behind the others.

Reproduce with the `forge-audit` fleet command above, or `make dogfood-fleet` in the
`forge-audit` repo.
