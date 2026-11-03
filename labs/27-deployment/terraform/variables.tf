variable "region" {
  description = "AWS region. us-east-1 is the cheapest; il-central-1 (Tel Aviv) exists but costs more."
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Name prefix for every resource."
  type        = string
  default     = "company-brain"
}

variable "image_tag" {
  description = "Tag of the image in ECR to run. Use the git SHA, never latest."
  type        = string
  default     = "v1"
}

variable "container_port" {
  type    = number
  default = 8000
}

variable "cpu" {
  description = "Task CPU units: 256 = 0.25 vCPU. Valid Fargate pairs: 256 with 512/1024/2048 MB."
  type        = number
  default     = 256
}

variable "memory" {
  description = "Task memory in MiB."
  type        = number
  default     = 512
}

variable "cpu_architecture" {
  description = "X86_64, or ARM64 (Graviton, about 20% cheaper) if you build the image for linux/arm64."
  type        = string
  default     = "X86_64"

  validation {
    condition     = contains(["X86_64", "ARM64"], var.cpu_architecture)
    error_message = "cpu_architecture must be X86_64 or ARM64."
  }
}

variable "desired_count" {
  description = "Tasks to start with. Autoscaling moves it between min_count and max_count."
  type        = number
  default     = 1
}

variable "min_count" {
  type    = number
  default = 1
}

variable "max_count" {
  type    = number
  default = 3
}

variable "requests_per_task_target" {
  description = "Autoscaling target: average ALB requests per task per minute."
  type        = number
  default     = 60
}

variable "llm_model" {
  description = "llmkit model spec the service uses."
  type        = string
  default     = "anthropic:claude-haiku-5-5"
}

variable "allowed_cidr" {
  description = "Who may reach the load balancer. Put your own IP here (curl ifconfig.me)/32 for the lab."
  type        = string
  default     = "0.0.0.0/0"
}

variable "log_retention_days" {
  type    = number
  default = 7
}
