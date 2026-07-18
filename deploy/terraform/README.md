# Deploying CodeForge as code (Terraform)

Portable infrastructure-as-code for the CodeForge container: `terraform apply`
pulls the published image, creates a named volume for canonical state, and runs
the engine with the port and env the Dockerfile expects. `terraform destroy`
removes it cleanly. This is the vendor-neutral peer of [`../../render.yaml`](../../render.yaml)
(the Render Blueprint that runs the public browser demo): same container, one
declarative spec that is not tied to a single host.

## What it provisions

| Resource | Purpose |
|---|---|
| `docker_image.codeforge` | the image (default: `ghcr.io/matrymlabs/codeforge:latest`, published by [`publish-image.yml`](../../.github/workflows/publish-image.yml)) |
| `docker_volume.state` | a named volume for `/data` (canonical state survives a container replace) |
| `docker_container.codeforge` | the running engine, telnet gateway on port 4000 |

Every knob (image, port, seed, volume) is a variable, so a deploy is a values
file, not a code edit. See [`variables.tf`](variables.tf).

## Run it

```bash
cd deploy/terraform
cp terraform.tfvars.example terraform.tfvars   # optional: override defaults
terraform init
terraform plan       # preview
terraform apply      # provision on the local Docker daemon
# ... connect a MUD client to localhost:4000 ...
terraform destroy    # tear down
```

The Docker provider targets whatever `DOCKER_HOST` points at, so the same config
deploys to a remote daemon (a cloud VM) by exporting `DOCKER_HOST=ssh://user@host`
before `apply` - no rewrite.

## The honest envelope

- **CI validates, it does not apply.** The `terraform` job in CI runs
  `fmt -check`, `init`, and `validate` on every change, so the config is proven
  well-formed. It does not stand up infrastructure (that needs a Docker daemon
  and the published image).
- **The live public demo runs on Render** via `render.yaml`, not this module.
  This is the portable IaC that provisions the *same* container anywhere a Docker
  daemon is reachable; a live `terraform apply` to a cloud host is a deliberate,
  separately-decided step (it needs an account and may bill).
- **`.terraform.lock.hcl` is committed** (multi-platform hashes) so the provider
  version is reproducible; `terraform.tfvars` and state are git-ignored.
