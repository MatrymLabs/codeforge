# Inputs. Every knob the Dockerfile documents (port, seed, state volume) is a
# variable here, so a deploy is a values file, not an edit to the code.

variable "image" {
  description = "Container image to run. Defaults to the image published to GHCR by the publish-image workflow."
  type        = string
  default     = "ghcr.io/matrymlabs/codeforge:latest"
}

variable "container_name" {
  description = "Name for the running container."
  type        = string
  default     = "codeforge"
}

variable "host_port" {
  description = "Host port to publish the telnet gateway on (container listens on 4000)."
  type        = number
  default     = 4000
}

variable "forge_seed" {
  description = "Which world the engine boots (matches FORGE_SEED)."
  type        = string
  default     = "aethryn"
}

variable "data_volume" {
  description = "Named Docker volume for canonical state (/data), so it survives a container replace."
  type        = string
  default     = "codeforge_data"
}
