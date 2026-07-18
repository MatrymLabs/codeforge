# A Render web service, managed as code, running the published GHCR image with
# the browser (WebSocket) gate - the same container the local-docker module and
# the render.yaml Blueprint run. This is a SEPARATE service (codeforge-iac) from
# the live demo (codeforge-demo), so applying it never touches the public demo.
#
# The provider reads RENDER_API_KEY from the environment; export it before apply:
#   export RENDER_API_KEY=rnd_...    # your Render API key (never commit it)
#   terraform apply

provider "render" {
  owner_id = var.render_owner_id
}

resource "render_web_service" "codeforge" {
  name   = var.service_name
  plan   = var.plan
  region = var.region

  # Deploy a prebuilt image from GHCR (public, so no registry credential needed).
  runtime_source = {
    image = {
      image_url = var.image
    }
  }

  # Override the container entrypoint to the browser gate, which binds Render's
  # injected $PORT (mirrors render.yaml's dockerCommand). /health is the probe.
  start_command     = "codeforge web"
  health_check_path = "/health"

  # Ephemeral demo DB in tmp so a public link never accretes accounts.
  env_vars = {
    CODEFORGE_DB = { value = "/tmp/codeforge-demo.db" }
    FORGE_SEED   = { value = var.forge_seed }
  }
}
