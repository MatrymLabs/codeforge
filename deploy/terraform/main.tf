# The whole deployment, declared. `terraform apply` pulls the published image,
# creates a named volume for canonical state, and runs the container with the
# port + env the Dockerfile expects. `terraform destroy` removes it cleanly.
# State is canonical and lives on the volume; the container is replaceable.

resource "docker_image" "codeforge" {
  name = var.image
}

resource "docker_volume" "state" {
  name = var.data_volume
}

resource "docker_container" "codeforge" {
  name    = var.container_name
  image   = docker_image.codeforge.image_id
  restart = "unless-stopped"

  # Telnet gateway. The container's CMD is `spark` (the LAN telnet server).
  ports {
    internal = 4000
    external = var.host_port
  }

  # Every value the Dockerfile documents, passed as config not baked in.
  env = [
    "FORGE_SEED=${var.forge_seed}",
    "CODEFORGE_DB=/data/codeforge.db",
  ]

  # Canonical state on a named volume so a container replace does not lose it.
  volumes {
    volume_name    = docker_volume.state.name
    container_path = "/data"
  }

  healthcheck {
    test     = ["CMD-SHELL", "true"] # the engine has no in-container HTTP health probe on the telnet gate; liveness is the process
    interval = "30s"
    timeout  = "5s"
    retries  = 3
  }
}
