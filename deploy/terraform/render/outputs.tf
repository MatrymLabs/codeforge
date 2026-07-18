output "service_id" {
  description = "Render service ID."
  value       = render_web_service.codeforge.id
}

output "url" {
  description = "Public URL of the deployed service."
  value       = render_web_service.codeforge.url
}
