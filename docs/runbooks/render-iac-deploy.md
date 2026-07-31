# Runbook: deploy the codeforge-iac Render service

*A checklist for applying the Terraform-managed Render web service (`codeforge-iac`), the
infrastructure-as-code sibling of the public demo. It deploys the hardened, signed GHCR image and
verifies its provenance before it goes live.*

| Field | Value |
|-------|-------|
| **System** | the `codeforge-iac` Render web service (`deploy/terraform/render`) |
| **Owner** | Josh / MatrymLabs |
| **Last reviewed** | 2026-07-31 |
| **Risk** | medium (reconciles a live Render service; SEPARATE from the public `codeforge-demo`, so this never touches the demo) |

## When to use this

You want to create or update the `codeforge-iac` service from code: a new image is published, a
config change landed in `deploy/terraform/render`, or you are standing the service up fresh.

## Why a runbook (and not automation)

`terraform apply` reconciles a **live** Render service and needs the **`RENDER_API_KEY`** secret,
which is deliberately never committed and is yours alone. So the apply is a **human-run, one-command
step** - CI only ever validates the config, it never applies. That separation is the point: the
pipeline proposes, you release.

## Preconditions

- [ ] Terraform installed (`terraform version` -> v1.9.x, matching CI).
- [ ] `RENDER_API_KEY` exported in your shell (`export RENDER_API_KEY=rnd_...`) - never into a file.
- [ ] `RENDER_OWNER_ID` known (or pass `-var render_owner_id=...`).
- [ ] `gh` authenticated (for the provenance check below).
- [ ] On `main`, clean tree, CI green - so the image you are about to deploy is the reviewed one.

## Procedure

1. **Verify the image's provenance BEFORE deploying it.** Prove the GHCR image was built from this
   repo and commit by the publish workflow, and is not substituted (see the signing in #677):
   ```bash
   gh attestation verify oci://ghcr.io/matrymlabs/codeforge:latest --repo MatrymLabs/codeforge
   ```
   Expect: `1 attestation verified` with `predicateType: https://slsa.dev/provenance/v1`.
   **If this fails, STOP** - do not deploy an unverifiable image; go to incident Playbook 3.

2. **Validate + plan (read-only; shows exactly what will change):**
   ```bash
   cd deploy/terraform/render
   terraform init
   terraform validate            # already green in CI; re-confirm locally
   terraform plan -out tf.plan    # REVIEW the plan: it should touch only render_web_service.codeforge
   ```

3. **Apply the reviewed plan (the live reconcile - your call):**
   ```bash
   terraform apply tf.plan
   ```

4. **Capture the outputs:**
   ```bash
   terraform output url          # the public URL of the service
   terraform output service_id
   ```

## Verify it worked

- [ ] `terraform apply` reports success with no unexpected replacements.
- [ ] `curl -sf "$(terraform output -raw url)/health"` returns `{"status":"alive", ...}`.
- [ ] The page at the service URL loads the terminal and carries the security headers:
      `curl -sI "$(terraform output -raw url)/" | grep -i 'content-security-policy\|x-frame-options'`.

## Rollback

If the new deploy is worse, redeploy the previous known-good image or revert the config change, then
re-apply:
```bash
# Option A - roll the image back to a known-good digest/tag:
terraform apply -var image_tag=<previous-good-sha-or-digest>

# Option B - revert the offending config commit, then:
terraform plan -out tf.plan && terraform apply tf.plan

# Option C - fastest, no code: pause or roll back in the Render dashboard (Deploys tab).
```
State is ephemeral (demo DB in `/tmp`), so a rollback loses no user data.

## Escalate if

- `gh attestation verify` fails - treat as a supply-chain incident (Playbook 3), do not deploy.
- `terraform plan` shows a destructive change you did not expect (a resource replacement, an identity
  change) - stop and review before applying.
- The rollback itself fails, or the service will not come healthy on a known-good image.

## Related

- [`incident-response.md`](incident-response.md) - Playbook 3 (artifact substitution), Playbook 5
  (live-service abuse).
- [`demo-deploy-rollback.md`](demo-deploy-rollback.md) - the public `codeforge-demo` (Blueprint) path.
- `deploy/terraform/render/README.md` - the module's own notes.
