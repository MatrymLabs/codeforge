# VeritasGate — `truth check`

*No claim without correspondence.* The intellect must conform to the thing; the README
must conform to the code; the claim must conform to the evidence.

```bash
# in the MUD:
truth check
```

`truth check` composes the truth-relevant signals the repo already produces into one
honest verdict. It **reports** mismatches — it never hides them, and never asserts more
than the evidence supports.

## What it checks

| Claim | Signal | Verified when |
|-------|--------|---------------|
| README/docs avoid unqualified compliance / production claims | `overclaim_hits` | no forbidden words ("production-ready", "certified", "…compliant", …) |
| README makes no drift-prone hardcoded test count | regex scan | no `\d+ tests` — the CI badge is the live source (the exact count drifted 3×) |
| Key documentation is present | `presence_gaps` | README · CHANGELOG · SECURITY · CONTRIBUTING · docs present |
| Classification registry validates | `validate()` | no duplicate / orphaned designations |
| QA board has no failing objects | `qa gate all` | every `active` object is backed by a file + tests |

Verdict: **ALL VERIFIED** (claims correspond to reality) or **N FLAGGED** (correct the
claim, or the code, before trusting it).

## Boundaries

- It keeps **CodeForge's own claims** honest. It does **not** prove legal originality,
  security, or compliance — those need qualified human review (see
  [legal_policy_awareness](legal_policy_awareness.md)).
- It composes, it doesn't duplicate: the broader [RepoIntegrityRitual](repo_integrity.md)
  (`make repo-integrity`) reports the full repo health; `truth check` is the focused
  claims-vs-reality gate you can run in the MUD.
