# Frame-Up Inspection (`inspect`)

*Inspect the forge: an on-demand green/yellow/red frame-up of every major system, in one
view. Nothing stored, nothing faked — computed live from the project's own gates.*

## In the MUD

```
inspect            # the frame-up
inspect forge      # same — "inspect the forge"
```

## What it composes

`parts/frameup.py` **reuses** the existing self-audit signals (it does not duplicate them),
and rolls them into one verdict:

| System | Signal | Green when |
|--------|--------|-----------|
| Classification registry | `validate(load_collective())` | no duplicates/orphans |
| Quality gate (QA board) | `gate_all()` | all `pass` (any `watch` → yellow, any `fail` → red) |
| VeritasGate (truth) | `truth_checks()` | every claim verified |
| Documentation | `presence_gaps()` | key docs present |
| Overclaim scan | `overclaim_hits()` | no unqualified compliance/production claims |
| Career board *(info)* | `career.load_board()` | always shown; gaps are honest, not failures |
| Pioneer mode *(info)* | filed experiments count | always shown |

**Overall** = worst of the *gating* systems (registry · QA · truth · docs · overclaim).
The two **info** rows (career, pioneer) report status but never drag the verdict down —
career *gaps* are honestly-tracked, not defects.

## Why it exists

CodeForge grew many self-audit systems (`pm status`, `qa gate`, `truth check`, `career`,
`pioneer`, `make repo-integrity`). `inspect` is the **single pane of glass** over all of
them — the fastest honest answer to "how healthy is the whole machine right now?" It gives
the gates one view; it does not replace them. Same spirit as `make repo-integrity`, but
surfaced in-MUD as a command and framed as a systems inventory.

## Relation to the written Frame-Up Audit

`inspect` is the *automated, live* frame-up. The deeper, judgment-based engineering review
(consolidation opportunities, choice-by-choice overrides, priorities) is a human audit —
see the Frame-Up Audit report when one is run. The command keeps the machine honest between
audits.
