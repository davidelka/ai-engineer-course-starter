variable "region" {
  description = "AWS region. us-east-1 is the cheapest and the one the cost model is priced for."
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Name prefix for every resource."
  type        = string
  default     = "company-brain"
}

variable "image_tag" {
  description = "Tag of the image in ECR (the git SHA, never latest). Build target runtime-e5 for live mode."
  type        = string
  default     = "v1"
}

variable "container_port" {
  type    = number
  default = 8000
}

variable "cpu" {
  description = "512 = 0.5 vCPU. With the e5 image the first start embeds 404 chunks: 0.5 vCPU is enough."
  type        = number
  default     = 512
}

variable "memory" {
  description = "MiB. 2048: PyTorch + e5-small + LangGraph fit with room. Valid with 512 CPU: 1024-4096."
  type        = number
  default     = 2048
}

variable "mode" {
  description = "MODE of the brain: live (Haiku via the gateway) or offline (free, a smoke test of the infrastructure)."
  type        = string
  default     = "live"

  validation {
    condition     = contains(["live", "offline"], var.mode)
    error_message = "mode must be live or offline."
  }
}

variable "allowed_cidr" {
  description = "Who may reach the load balancer: YOUR IP/32 (curl ifconfig.me). The brain has its own API keys, but HTTP is not encrypted."
  type        = string
}

variable "log_retention_days" {
  type    = number
  default = 14
}

variable "budget_limit_usd" {
  description = "Monthly cost budget for this stack (alerts at 50%, 100% and forecasted 100%). The stack costs ~$51/month."
  type        = number
  default     = 60
}

variable "alert_email" {
  description = "Where the budget alerts go."
  type        = string
}
