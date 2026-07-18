# Deploying CodeForge to Render as code (Terraform)

Manages a live Render web service running the published GHCR image, declared in
Terraform. This is the cloud counterpart to the local-docker module one level up:
same container, a real hosted target, managed as code instead of clicked in a
dashboard.

It provisions a **separate** service (`codeforge-iac`), distinct from the live
demo (`codeforge-demo`, run by [`../../../render.yaml`](../../../render.yaml)), so
applying this never touches the public demo.

## What it provisions

| Resource | Purpose |
|---|---|
| `render_web_service.codeforge` | a Render web service running `ghcr.io/matrymlabs/codeforge:latest` with the browser gate (`codeforge web`), `/health` probe, ephemeral demo DB |

## Apply it (needs your Render account)

**One command:** `./deploy.sh` (prompts for your API key, derives the owner id, runs the guarded apply). Or do it by hand:

The provider reads the API key from the environment, so the secret never enters a
`.tf` file, `terraform.tfvars`, or state:

```bash
cd deploy/terraform/render
export RENDER_API_KEY=rnd_xxxxxxxx        # Render dashboard -> Account Settings -> API Keys
export RENDER_OWNER_ID=tea_xxxxxxxx       # your workspace owner id (or set render_owner_id in tfvars)
terraform init
terraform plan                            # preview: creates one free web service
terraform apply                           # go live
terraform output url                      # the public URL
# ... roll back / tear down:
terraform destroy
```

## Refreshing to a newer image

The service deploys `ghcr.io/matrymlabs/codeforge:latest`, but Render pulls the image
at deploy time and does **not** auto-pull a new `:latest` on its own (the Render Terraform
provider does not expose an auto-deploy flag for image sources, only for repo/Dockerfile
sources). So after CI republishes the image, refresh the running service one of two ways:

- **Redeploy from here:** re-run `terraform apply` pointing at a fresh tag or digest, e.g.
  `terraform apply -var 'image_tag=<new-sha>'` (a changed tag forces a new deploy), or
- **Render dashboard:** the service's *Manual Deploy -> Deploy latest reference*, or turn on
  the service's own auto-deploy there.

The public browser demo (`codeforge-demo`, `render.yaml`) is a repo/Dockerfile source and
already auto-deploys on every push to `main`; this image-based service is the deliberate
tradeoff for deploying a *prebuilt, pinned* artifact.

## Cost + safety

- **Plan is `free`.** A Render free web service does not bill, and it sleeps when
  idle (same tier as the existing demo). No paid resource is created by the
  defaults here.
- **The live demo is never touched:** this is a distinct service name, distinct
  Terraform state.
- **The secret stays out of git:** API key via `RENDER_API_KEY` env only;
  `terraform.tfvars` and state are git-ignored; `.terraform.lock.hcl` is committed
  for a reproducible provider version.
- **CI validates, it does not apply.** The `terraform` CI job runs `validate` on
  this module; standing up the service is a deliberate, credentialed local step.
