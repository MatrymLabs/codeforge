# Runbook: security incident response

*Playbooks for the security incidents most likely to hit CodeForge and the MAT Labs fleet. Each is a
checklist that runs the same way at 3pm and at 3am. This is process documentation, not a compliance
claim: it records how we would respond, and it is exercised by drills, not certified by an assessor.*

| Field | Value |
|-------|-------|
| **System** | CodeForge engine + the public demo + the build/publish pipeline + fleet repos |
| **Owner** | Josh / MatrymLabs |
| **Last reviewed** | 2026-07-31 |
| **Risk** | high (this is the response of last resort) |

## Roles and authority

Solo-development reality: **Josh is the incident commander and the only release/revocation authority.**
ClaudiB (the AI assistant) may detect, investigate, propose, and prepare fixes, but **may not**
revoke a credential, force a release, weaken a gate, or approve its own change. Every consequential
action below is Josh's to execute.

## Severity model

| Sev | Meaning | Examples | First response target |
|-----|---------|----------|------------------------|
| **S1 critical** | secret exposed, build/artifact compromise, account/owner takeover | a signing/API key in git; a substituted image; a compromised dependency in a release | revoke in minutes, not the next dev cycle |
| **S2 high** | exploitable defect, live-demo compromise, dependency CVE reachable in prod | RCE-class bug; the public demo defaced or abused; a high CVE in a shipped dep | contain same day |
| **S3 moderate** | defect not yet exploitable, non-prod exposure | a high CVE in a dev-only dep; a flaky control | fix in the normal cycle |

## Universal first moves (every incident)

1. **Write it down from minute zero.** Open a dated note under `docs/reports/security/` (or a private
   issue). Record: what was seen, when, where, who is acting. Evidence discipline starts now.
2. **Contain before you clean.** Stop the bleeding (revoke, take offline, disable) before you
   investigate root cause. A running compromise is worse than a paused service.
3. **Preserve evidence.** Do not `git push --force` history or delete logs until the exposure window
   and blast radius are understood. Capture the offending commit, artifact digest, and timestamps.
4. **Fail closed.** If a control's state is unclear, treat it as failed and deny until proven safe.

---

## Playbook 1 - Credential or secret exposure (S1)

A key, token, password, or `.env` value reached somewhere it should not: git, a build log, a chat
transcript, an AI prompt, a container layer, or a public repo.

- **Detection:** `make secrets` (detect-secrets) fails; GitHub secret-scanning alert; a manual find; a
  provider's "leaked credential" notice.
- **Containment / revocation (do this FIRST, before cleanup):**
  ```bash
  # 1. REVOKE the exposed credential at its source (GitHub token, Render API key, Anthropic key,
  #    Codecov token, ...). Revoke first; a rotated-but-not-revoked key is still live.
  # 2. ROTATE: issue a replacement and update it only in the secret store / GitHub Actions secrets
  #    (never back into git).
  ```
- **Isolation:** disable any automation that used the key until the replacement is in place.
- **Determine exposure:** which commits/logs/artifacts contained it, and for how long. Assume any
  public-repo exposure was harvested by a bot within minutes.
- **Eradication:** remove the value from the working tree and config. Rewriting git history is a
  DESTRUCTIVE, approval-gated action (Josh only) and does not un-leak a public secret, so it comes
  *after* revocation, never instead of it.
- **Recovery / validation:** re-run `make secrets`; confirm the new credential works and the old one
  is dead (a call with the old key must fail).
- **Notification:** if the key granted access to a third party (Render, GHCR, Anthropic), check that
  provider's audit log for use during the exposure window.
- **Post-incident:** add the pattern to `.secrets.baseline` handling; confirm the pre-commit +
  server-side secret gates would have caught it; record the lesson.

## Playbook 2 - Malicious or vulnerable dependency (S1/S2)

A third-party package is compromised, yanked, or carries a reachable high/critical CVE.

- **Detection:** `make audit` / `make audit-runtime` (pip-audit) flags a CVE; an advisory; Scorecard
  or Dependabot.
- **Triage (beyond CVSS):** is the vulnerable code path actually reachable in CodeForge? Is it a
  runtime or dev-only dependency? A dev-only CVE is S3, not S1.
- **Containment:** pin to a fixed version, or remove the package if it is unused (dependencies earn
  their place; an unused one is pure attack surface).
  ```bash
  make patch          # scan deps, apply fixes to the venv, then re-run `make check` as the net
  make audit-runtime  # confirm the runtime tree is clean
  ```
- **Eradication / recovery:** land the pinned/removed dependency behind a green `make check`; rebuild
  and republish the image (which re-attests provenance, see Playbook 3).
- **Validation:** `make audit` clean; the app still passes its suite.
- **Post-incident:** if the package was abandoned, replace it (SSDF PW.4). Record why it was trusted.

## Playbook 3 - Build-pipeline compromise or artifact substitution (S1)

The published image may not be what this repo built: a tampered pipeline, a substituted image, or an
untrusted push to GHCR.

- **Detection:** an unexpected image digest; a failed provenance verification; a suspicious
  publish-image run.
- **Verify authenticity (this is why #677 exists):**
  ```bash
  # Prove the running/published image was built from THIS repo + commit by THE publish workflow.
  gh attestation verify oci://ghcr.io/matrymlabs/codeforge:latest --repo MatrymLabs/codeforge
  # A failure here (or a digest that does not match a known-good publish run) is the incident.
  ```
- **Containment:** stop deploying `latest`; pin the live demo / IaC service to a known-good digest
  that verifies. Rotate the GHCR `packages:write` token (Playbook 1) if a push was unauthorized.
- **Eradication:** delete the bad image version from GHCR; rebuild from a clean checkout; confirm the
  new artifact verifies.
- **Recovery / validation:** re-run the `docker` CI job (build + smoke) and re-verify provenance on
  the new digest. Deploy only a digest that passes `gh attestation verify`.
- **Post-incident:** confirm branch protection, SHA-pinned actions, and least-privilege workflow
  permissions held; if not, that is the root cause.

## Playbook 4 - Account or Seed-Owner compromise (S1/S2)

A player, or worse an owner/wizard, account is taken over.

- **Detection:** a login from nowhere; unexpected `@`-verb use in logs; a report.
- **Containment / revocation:** rotate the account's password (pbkdf2 rehash on the new secret); for
  an owner/wizard, demote the rank until verified. Authorization is server-side and rank-gated, so a
  demoted account loses privileged verbs immediately.
- **Isolation:** the demo is seat-capped, admin-free, and ephemeral, so a compromised *demo* visitor
  is only ever rank `player` and cannot escalate; the blast radius is one seat.
- **Evidence / recovery:** review the tick audit trail for the privileged actions taken; reverse any
  world/economy edits (state is canonical, so a restore from a known-good snapshot undoes them).
- **Post-incident:** confirm brute-force lockout + generic refusals held; raise the password floor if
  the account used a weak secret.

## Playbook 5 - Live-demo abuse, defacement, or denial of service (S2)

The public browser demo is being farmed, flooded, or shipped a bad deploy.

- **Detection:** the demo is down/slow, `/health` fails, or content looks wrong.
- **Containment:** the fastest lever is the deploy rollback - see
  [`demo-deploy-rollback.md`](demo-deploy-rollback.md). The demo is ephemeral (no user data to lose),
  so rolling back is safe and immediate.
- **Abuse resistance already in place:** seat cap (`MAX_CONNECTIONS`), idle timeout, ephemeral DB,
  no admin surface, WS output sanitized against terminal-escape injection, security response headers
  (#676). If abuse persists past these, take the service offline in the Render dashboard.
- **Recovery / validation:** redeploy the last-good commit; confirm `/health` returns and the login
  front desk works.
- **Post-incident:** if a specific abuse got through, add the abuse case as a test/limit and file it.

---

## Drills (exercise the process, do not just file it)

A playbook nobody has run is a wish. Run these periodically and record the result under
`docs/reports/security/`:

- **Credential-revocation drill:** rotate a low-stakes token end to end; time it (target: minutes).
- **Provenance-verification drill:** run `gh attestation verify` against the live image; confirm it
  passes for the real repo and fails for a wrong one.
- **Rollback drill:** roll the demo back and forward using `demo-deploy-rollback.md`.
- **Dependency-patch drill:** run `make patch` and confirm the gate re-verifies.

## Escalate / stop if

- The rollback or revocation itself fails.
- The exposure window or blast radius is unclear after containment.
- A destructive action (history rewrite, image deletion) is proposed - that is Josh's call, made with
  evidence in hand, never automatically.

## Related

- [`demo-deploy-rollback.md`](demo-deploy-rollback.md) - roll back the live demo.
- [`render-iac-deploy.md`](render-iac-deploy.md) - deploy the codeforge-iac service safely.
- [`../reports/security/control-crosswalk.yaml`](../reports/security/control-crosswalk.yaml) - the
  controls these incidents test.
- [`../reports/security/security-roadmap.md`](../reports/security/security-roadmap.md),
  [`../../SECURITY.md`](../../SECURITY.md) - reporting channel and hardening status.
