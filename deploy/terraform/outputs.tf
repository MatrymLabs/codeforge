output "container_name" {
  description = "Name of the running container."
  value       = docker_container.codeforge.name
}

output "endpoint" {
  description = "host:port the telnet gateway is reachable on."
  value       = "localhost:${var.host_port}"
}

output "image_digest" {
  description = "Resolved digest of the image actually running (provenance)."
  value       = docker_image.codeforge.repo_digest
}
