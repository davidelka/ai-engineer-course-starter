variable "region" {
  description = "AWS region. us-east-1 is the cheapest; il-central-1 (Tel Aviv) keeps student data in Israel but costs more."
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Name prefix for every resource."
  type        = string
  default     = "hebrew-tutor"
}

variable "image_tag" {
  description = "Tag of the image in ECR to run. Use the git SHA, never latest."
  type        = string
  default     = "v1"
}

variable "container_port" {
  type    = number
  default = 8080
}

variable "cpu" {
  description = "Task CPU units: 256 = 0.25 vCPU. The API waits on model and speech APIs; 0.25 vCPU is enough for a pilot."
  type        = number
  default     = 256
}

variable "memory" {
  type    = number
  default = 512
}

variable "tutor" {
  description = "rule (free, offline) or llm (Claude Haiku 5.5)."
  type        = string
  default     = "llm"
}

variable "stt" {
  description = "fake or openai. (local faster-whisper needs a bigger task and a different image.)"
  type        = string
  default     = "openai"
}

variable "tts" {
  description = "fake or openai. OpenAI's gpt-4o-mini-tts shuts down on 2027-01-06: plan the replacement."
  type        = string
  default     = "openai"
}

variable "llm_model" {
  type    = string
  default = "anthropic:claude-haiku-5-5"
}

variable "retention_days" {
  description = "Days to keep (redacted) turn text. Progress and points stay."
  type        = number
  default     = 30
}

variable "allowed_cidr" {
  description = "Who may reach the load balancer. Your school's public IP range, or your own IP /32 for testing."
  type        = string
  default     = "0.0.0.0/0"
}

variable "certificate_arn" {
  description = "ACM certificate for your domain. Empty = HTTP only, and then the browser blocks the microphone (MediaRecorder needs a secure context)."
  type        = string
  default     = ""
}

variable "log_retention_days" {
  type    = number
  default = 7
}
