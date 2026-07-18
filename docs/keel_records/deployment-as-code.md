# Keel Record: Deployment as code (Terraform + GHCR)

*Human Keel Record (see [../human_keel_doctrine.md](../human_keel_doctrine.md)). This documents a
critical-junction design decision and its first build slice. Per the doctrine, AI proposes and Josh
approves; **AI does not assign ownership**. The level-4 ownership claim and the "what I learned"
reflection below are left for Josh to complete when he can defend the design to an interviewer.*

- **Build:** portable infrastructure-as-code for the CodeForge container - a Terraform module
  (`deploy/terraform/`, `kreuzwerker/docker` provider) that provisions the published image, plus a
  GHCR publish workflow (`.github/workflows/publish-image.yml`) and a CI `terraform` validate job.
  Recorded in [ADR-0009](../adr/0009-deployment-as-code.md).
- **Ownership level claimed:** *(pending Josh's own claim; undeclared until he defends it)*

## Intent
Close the two platform-engineering gaps the existing deploy story left open: the only IaC was the
Render Blueprint (proprietary to one host), and the image was built in CI but never published. Add
portable Terraform + a pullable GHCR image so a platform reviewer sees industry-standard IaC, a
published artifact, and a validation gate - the skills the resume alignment map had to leave in the
"currently learning" column.

## Problem
`render.yaml` is real IaC but vendor-specific; a Backend/Platform screen wants Terraform. And with no
published image, every deploy rebuilds from source and nothing external can run CodeForge.

## Constraints
- **Delivery mechanics, not an engine feature** - must fit within the codeforge freeze (engine
  untouched).
- **No spend, no accounts, reversible** for this slice: CI validates the IaC but does not apply it;
  a live cloud `apply` is a separate, deferred decision that needs an account and may bill.
- Match the repo's conventions (action-free raw `docker` CLI; SHA-pinned `actions/checkout`).

## Alternatives considered
- **Terraform against a cloud provider now (AWS/GCP + real apply).** Strongest signal, but costs
  money, needs an account, and is not reversible for free. Deferred to a separate decision.
- **A managed-platform action (fly.io / Render Terraform provider) with a live apply.** Same account
  and billing concern; also couples the slice to one vendor. The Docker provider stays vendor-neutral
  (any `DOCKER_HOST`).
- **Do nothing / keep only render.yaml.** Leaves the Terraform gap the target role screens for.

## Evidence
- `terraform fmt/init/validate` green locally (v1.9.8) and gated in CI on every change.
- `.terraform.lock.hcl` committed with linux_amd64 + linux_arm64 + darwin_arm64 hashes (reproducible).
- The publish workflow uses the same raw `docker` build the CI `docker` job already smoke-tests.

## What I learned / uncertainty
*(left for Josh - e.g. the DOCKER_HOST portability point, or why CI validates but does not apply)*

## Review point
When a live cloud deploy is wanted, this module is the base: point `DOCKER_HOST` at a remote daemon,
or add a cloud provider block. That apply is its own keel decision with its own evidence.
