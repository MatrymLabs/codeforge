# Postmortem: a red security gate reached `main`

*Blameless. The system let a merge land that its own CI would reject; we fixed the system
so that class of mistake is caught before merge, not after.*

| Field | Value |
|-------|-------|
| **Date** | 2026-07-09 |
| **Status** | closed |
| **Authors** | Josh / MatrymLabs (AI-assisted) |
| **Severity** | SEV3 (default branch CI red; no runtime/user impact - portfolio repo) |

## Summary

A change to `parts/integrity.py` merged to `main` and turned CI **red**: bandit's `B105`
(hardcoded-password) check fired on a dictionary literal `{"pass": 0, ...}`, reading the
key `"pass"` as a password. The pre-merge check passed locally because the **local gate
did not run bandit** - CI's `make security` did.

## Impact

The `main` branch showed a **failing CI badge** for the length of one fix-forward cycle.
No runtime impact (portfolio repo, no users), but a red default branch is a real defect for
a repo whose whole thesis is "green, evidence-backed engineering."

## Timeline (UTC)

| Time | Event |
|------|-------|
| ~T+0 | `make check` (lint · types · tests) green locally; change merged to `main`. |
| ~T+2m | CI runs `make security` on `main`; **bandit B105 fails**; badge goes red. |
| ~T+5m | Detected by watching the post-merge CI run. |
| ~T+12m | Fix-forward committed (`Counter` instead of the `"pass"`-keyed literal); CI green. |

## Root cause

**Gate asymmetry.** The local pre-merge gate (`make check`) ran lint + types + tests, but
**not** bandit - while CI's `make security` did. So a bandit-only failure was structurally
invisible before merge. The trigger was a bandit false positive (`"pass"` as a dict key
read as a hardcoded password), but the *cause* is that the local gate proved less than the
pipeline gate, giving false assurance.

## Detection

Manual - watching the CI run after the merge. Detection was correct but *late*: it happened
**after** the code was already on `main`. The right time to catch it is before merge.

## Resolution

Replaced the `{"pass": 0, "watch": 0, "fail": 0}` literal with
`Counter(r.verdict for r in gate_all(records))`, which computes the same counts without a
string literal bandit could misread. Committed as a `fix:`, watched CI to green.

## What went well / what went wrong / where we got lucky

- **Went well:** CI's `make security` *did* catch it - the pipeline gate was correct and
  loud. Fix-forward was fast and honest (no history rewrite, no hiding).
- **Went wrong:** the local gate and the CI gate were not the same set, so "green locally"
  did not mean "green in CI." The merge happened without watching CI to green first.
- **Got lucky:** it was a false positive, not a real committed secret. Had the same gap hidden
  a *real* secret, the exposure window would have been the same.

## Action items

| Action | Type | Owner | Status |
|--------|------|-------|--------|
| Run **both** `make check` **and** `make security` before every merge | prevent | Josh | **done** (adopted as standing practice) |
| Watch CI to green **before** merging, never after | prevent | Josh | **done** |
| Give the startup ritual **gate parity** with CI (coverage folded into `check`; SAST + secrets in WARDS) | prevent | Josh | **done** (see `docs/startup_ritual.md`) |
| Add a shutdown **push-ready gate** that blocks on red gates / secrets | detect | Josh | **done** (see `docs/shutdown_ritual.md`) |

## Lessons

**A local gate that proves *less* than the pipeline gives false assurance - make them the
same set.** This incident is the origin of two standing rules now baked into the tooling:
the ritual asserts what CI asserts (gate parity), and nothing merges to `main` without
watching CI to green. The class of "green locally, red in CI" is now closed by construction.
