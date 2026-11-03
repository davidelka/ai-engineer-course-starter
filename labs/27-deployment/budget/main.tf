# A monthly cost budget with e-mail alerts. Create it FIRST, before anything that costs
# money, and do NOT destroy it with the lab: it is a separate root module on purpose,
# so `terraform destroy` in ../terraform leaves it watching the account.
#
#   cd labs/27-deployment/budget
#   terraform init
#   terraform plan  -var alert_email=you@example.com -out=tfplan
#   terraform apply tfplan
#
# Cost: AWS Budgets monitoring and notifications are free.
# Limits you must know: billing data refreshes a few times a day, so an alert can arrive
# hours after the spending started. A budget ALERTS; it does not stop anything by itself.

terraform {
  required_version = ">= 1.11"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

variable "alert_email" {
  description = "Where the alerts go. AWS sends no confirmation for budget e-mails."
  type        = string
}

variable "monthly_limit_usd" {
  description = "The lab costs about $1.25 per day while it is up; $10 catches a stack you forgot."
  type        = number
  default     = 10
}

resource "aws_budgets_budget" "monthly" {
  name         = "ai-engineer-course-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_limit_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  # Actual spend passed half the limit: something is running.
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 50
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }

  # Actual spend passed the limit.
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }

  # AWS FORECASTS the month will pass the limit: the earliest warning you can get.
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.alert_email]
  }
}

output "budget" {
  value = aws_budgets_budget.monthly.name
}
