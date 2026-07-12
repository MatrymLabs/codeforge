# Template: Infrastructure as code

**Use when:** deployment outgrows the single Render demo and needs declarative, versioned infra
(Terraform, Kubernetes, Helm). **Status for CodeForge:** deferred by design. The portfolio plan
holds advanced infra (Terraform/cloud beyond the existing Render demo) until the portfolio page
is live: an interviewer sees presentation before architecture. This template waits for that
trigger.

## Layout

```text
infra/                        # or deploy/ - always separate from application code
  terraform/
    main.tf                   # resources
    variables.tf              # inputs
    outputs.tf                # outputs
    terraform.tfvars.example  # committed; real .tfvars is gitignored
  k8s/
    deployment.yaml
    service.yaml
  helm/                       # optional, if templating charts
    Chart.yaml
    values.yaml
    templates/
.github/workflows/infra.yml   # terraform fmt + validate (+ plan on PR)
```

## Boundaries

- **Infra never mixes with app code.** It lives under one clear directory (`infra/` or
  `deploy/`), so a reader never confuses "how it deploys" with "what it does."
- **State and secrets stay out of git.** `*.tfstate` is gitignored; only `*.tfvars.example` is
  tracked. This is the same discipline as the ship's `.env` / `.env.example` rule.
- **CI gates infra too.** `terraform fmt -check` and `terraform validate` on every PR; a `plan`
  step for review. Apply is deliberate and human-approved, never automatic on merge.

## How this maps onto CodeForge if adopted

- Today's deploy is `render.yaml` + `Dockerfile` + `docker-compose.yml` at the root - correct
  for the current single-service demo.
- The trigger to adopt this template is a real multi-service or cloud deployment, **after** the
  portfolio page is live. Until then, creating an `infra/` tree would be the empty-folder
  anti-pattern.
- Adoption is a critical juncture (new tooling, cloud credentials, a security boundary): ADR +
  approval first.
