# Pin Terraform and the Docker provider. The Docker provider talks to a Docker
# daemon (local or remote over DOCKER_HOST), so the same config that runs the
# container on this machine runs it on a cloud VM by pointing DOCKER_HOST at it.
terraform {
  required_version = ">= 1.5"
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

provider "docker" {}
