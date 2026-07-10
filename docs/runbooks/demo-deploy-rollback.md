# Runbook: roll back the live demo deploy

*A runbook is a checklist for a known operation, so it runs the same way at 3pm and at 3am.
This one rolls the public browser demo back to a known-good state.*

| Field | Value |
|-------|-------|
| **System** | the public CodeForge browser demo (Render, from `main` via `render.yaml`) |
| **Owner** | Josh / MatrymLabs |
| **Last reviewed** | 2026-07-10 |
| **Risk** | medium (public-facing; state is ephemeral so no data loss) |

## When to use this

A deploy to `main` made the live demo worse: it fails to boot, the login front desk is
broken, or a security regression shipped. The demo serves an ephemeral, seat-capped,
admin-free surface, so there is no user data to lose, the goal is only to restore a working
public link fast.

## Preconditions

- [ ] You can reach the [Render dashboard](https://dashboard.render.com/) for the demo service.
- [ ] You know the last-good commit (check CI: the last `main` run that was green and behaved).
- [ ] Local tree clean, on `main`, in sync with origin.

## Procedure

### Option A - roll back on Render (fastest, no code change)

1. Render dashboard, the demo service, `Deploys` tab.
2. Find the last deploy that was healthy, use **`Rollback to this deploy`** (or `Redeploy`).
3. Watch the deploy log until it reports the gateway listening, then verify (below).

### Option B - revert the bad commit, let CI redeploy (fixes `main` too)

1. Identify the bad commit or merge:
   ```bash
   git log --oneline -10
   ```
2. Revert it on a branch, gate, merge, push (never force):
   ```bash
   git checkout -b fix/demo-rollback
   git revert --no-edit <bad-merge-sha>     # use -m 1 for a merge commit
   make check                                # must be green before pushing a "fix"
   git checkout main && git merge --no-ff fix/demo-rollback -m "Revert <what>; restore the demo"
   git push origin main                      # Render auto-deploys main
   ```
3. Watch CI green, then the Render deploy, then verify.

## Verify it worked

- [ ] The demo URL (https://codeforge-demo-1kcu.onrender.com/) loads the ASCII splash and a login prompt (allow ~30-60s for a cold start).
- [ ] Logging in reaches the world (`NEW` to make a character).
- [ ] `make smoke` passes locally against the reverted code (end-to-end sanity).

## Escalate if

- Both rollback options fail to produce a healthy deploy, stop and diagnose the Dockerfile /
  `render.yaml` rather than repeatedly redeploying.
- The regression was a leaked secret or an auth bypass, treat the secret as compromised
  (rotate it), do not merely roll back.

## Related

- [Startup ritual](../startup_ritual.md) and [shutdown ritual](../shutdown_ritual.md) (the push-ready gate).
- [Runbook template](../runbook_template.md) - copy it for the next operation.
- [Postmortem template](../postmortem_template.md) - write one if the bad deploy caused impact.
