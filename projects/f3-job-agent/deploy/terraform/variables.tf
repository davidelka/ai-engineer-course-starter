variable "region" {
  description = "AWS region. us-east-1 is the cheapest; the schedule's time zone is independent of it."
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Name prefix for every resource."
  type        = string
  default     = "job-agent"
}

variable "image_tag" {
  description = "Tag of the image in ECR. Use the git SHA, never latest."
  type        = string
  default     = "v1"
}

variable "schedule_timezone" {
  description = "IANA time zone of the cron expressions. EventBridge Scheduler handles DST in this zone."
  type        = string
  default     = "Asia/Jerusalem"
}

variable "slots" {
  description = "Run times (local to schedule_timezone). One EventBridge schedule per entry."
  type        = map(object({ hour = number, minute = number }))
  default = {
    "0830" = { hour = 8, minute = 30 }
    "1500" = { hour = 15, minute = 0 }
    "2100" = { hour = 21, minute = 0 }
  }
}

variable "schedules_enabled" {
  description = "false = keep everything but stop the runs (state DISABLED)."
  type        = bool
  default     = true
}

variable "extractor" {
  description = "heuristic (free) or llm (Claude Haiku 5.5, needs the API key parameter)."
  type        = string
  default     = "llm"

  validation {
    condition     = contains(["heuristic", "llm"], var.extractor)
    error_message = "extractor must be heuristic or llm."
  }
}

variable "llm_model" {
  type    = string
  default = "anthropic:claude-haiku-5-5"
}

variable "cpu" {
  type    = number
  default = 256
}

variable "memory" {
  type    = number
  default = 512
}

variable "log_retention_days" {
  type    = number
  default = 14
}
