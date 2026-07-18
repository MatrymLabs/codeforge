# Inputs for the Render-managed deployment. The API key is NOT here on purpose:
# the provider reads it from the RENDER_API_KEY env var, so the secret never
# enters a .tf file, terraform.tfvars, or state.

variable "render_owner_id" {
  description = "Render workspace/owner ID that owns the service (or set RENDER_OWNER_ID). Required for apply; find it in the Render dashboard URL or via the API."
  type        = string
  default     = null
}

variable "service_name" {
  description = "Name of the Render web service. Deliberately distinct from the live demo (codeforge-demo) so this never touches it."
  type        = string
  default     = "codeforge-iac"
}

variable "region" {
  description = "Render region."
  type        = string
  default     = "oregon"
}

variable "plan" {
  description = "Render instance plan."
  type        = string
  default     = "free"
}

variable "image" {
  description = "Image repository to deploy (WITHOUT the tag). The public GHCR image published by the publish-image workflow."
  type        = string
  default     = "ghcr.io/matrymlabs/codeforge"
}

variable "image_tag" {
  description = "Image tag to deploy (the Render provider requires the tag as its own field, not in image_url)."
  type        = string
  default     = "latest"
}

variable "forge_seed" {
  description = "Which world the engine boots (matches FORGE_SEED)."
  type        = string
  default     = "aethryn"
}
