# Final project F3: the job agent as an ECS Fargate SCHEDULED TASK (no service, no load balancer).
#
#   terraform init
#   terraform plan -out=tfplan      # read it: about 25 resources, none billed per hour while idle
#   terraform apply tfplan
#   terraform destroy               # when you are done showing it
#
# What runs: EventBridge Scheduler starts one task at 08:30, 15:00 and 21:00 Asia/Jerusalem.
# The task downloads the state (SQLite) and the WhatsApp exports from S3, runs one slot, writes
# the digest to S3 and uploads the state with If-Match. It exits after a minute or two.
# Cost: see `python -m jobagent cost` (well under $1 a month, plus tokens).
#
# Same patterns as lesson 27 (labs/27-deployment/terraform): default VPC, public subnet with a
# public IP instead of a NAT gateway, two IAM roles with least privilege, logs with retention.

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
  region = var.region

  default_tags {
    tags = {
      Project   = var.project
      Lesson    = "F3"
      ManagedBy = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}
