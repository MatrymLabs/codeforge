# ADR-0009: Deployment as code

**Status:** accepted (revisable - a scope choice about how far the delivery mechanics go)

## Context

CodeForge already ships real delivery mechanics: a multi-arch, non-root `Dockerfile`, a
`docker-compose.yml` for local orchestration, a `render.yaml` Blueprint that runs the public
browser demo, and a deploy/rollback runbook. That is a solid, honest deployment story, but it
has two gaps a platform reviewer notices:

1. The only infrastructure-as-code is the **Render Blueprint** - declarative, but proprietary
   to one host. There is no portable, industry-standard IaC (Terraform) a reviewer can read.
2. The container image is **built in CI but never published**, so nothing outside the repo can
   pull and run it; a deploy always rebuilds from source.

Closing these is a genuine platform-engineering slice, and it is *delivery mechanics, not a
new engine feature*, so it fits within the codeforge feature freeze (the engine is unchanged).

## Decision

Add **deployment as code** alongside the existing Dockerfile and Render Blueprint, without
replacing either:

1. **Publish the image to GHCR.** `.github/workflows/publish-image.yml` builds and pushes
   `ghcr.io/matrymlabs/codeforge` (commit-sha + `latest`) on merge to main and on version
   tags - not on PRs (a PR must not mutate the published `latest`). Raw `docker` CLI, matching
   the existing action-free `docker` job.
2. **Terraform module** (`deploy/terraform/`) using the `kreuzwerker/docker` provider: it
   pulls the published image, creates a named volume for canonical state, and runs the
   container with the port + env the Dockerfile documents. Every knob is a variable; the
   provider targets whatever `DOCKER_HOST` points at, so the same config runs the container
   locally or on a remote/cloud daemon with no rewrite.
3. **CI validates the IaC.** A `terraform` job runs `fmt -check`, `init`, and `validate` on
   every change. It does **not** apply (that needs a Docker daemon and the image); the config
   is proven well-formed, not stood up.

## The honest envelope

- The **live public demo runs on Render** via `render.yaml`, not this Terraform. The Terraform
  is the portable, vendor-neutral peer that provisions the *same* container anywhere.
- A live `terraform apply` to a cloud host is a **separate, deliberately-deferred step**: it
  needs a cloud account and may bill, so it is not part of this slice and not run in CI. When
  taken, it is its own decision with its own evidence.
- `.terraform.lock.hcl` is committed (multi-platform hashes) for reproducibility; state and
  `terraform.tfvars` are git-ignored.

## Consequences

- A platform reviewer can read real Terraform + a published, pullable image + a CI validation
  gate - the platform skills the Render Blueprint alone did not show.
- Nothing about the engine, the freeze, or the existing demo changes; this is additive.
- If a cloud target is later chosen, the module extends to it by pointing `DOCKER_HOST` at a
  remote daemon (or adding a cloud provider block) rather than starting over.
