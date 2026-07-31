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

  # Runtime hardening (defense in depth; the image already runs as non-root UID 10001).
  # Verified not to break the telnet server: it needs no Linux capability (a non-root high-port
  # bind) and never escalates privilege. Bounds a runaway from exhausting the host (a DoS control).
  security_opts = ["no-new-privileges:true"]
  memory        = 512 # MB
  capabilities {
    drop = ["ALL"]
  }

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

  # Real liveness: a plain TCP connect to the game port (the image's own HEALTHCHECK), so a hung
  # server is detected and `restart = unless-stopped` brings it back. The prior "CMD true" override
  # always reported healthy, which defeated the point.
  healthcheck {
    test     = ["CMD", "python", "-c", "import socket; socket.create_connection(('127.0.0.1', 4000), 3).close()"]
    interval = "30s"
    timeout  = "5s"
    retries  = 3
  }
}
