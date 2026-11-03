# Project F2: the spoken-Hebrew tutor API on AWS ECS Fargate behind an Application Load Balancer,
# with its SQLite file on EFS. Same patterns as lesson 27 (labs/27-deployment/terraform), adapted:
# one task only (SQLite has one writer), two API keys, EFS for /data, optional HTTPS.
#
#   terraform init
#   terraform plan  -out=tfplan     # ALWAYS read the plan before applying
#   terraform apply tfplan          # starts billing (about $0.05 per hour, see README)
#   terraform destroy               # stops billing; then run the teardown checklist
#
# State: local (terraform.tfstate in this folder, git-ignored). It contains resource IDs
# and can contain secrets, so never commit it. A team would use an S3 backend with
# locking (backend "s3" { use_lockfile = true }); for a one-person lab, local is fine.

terraform {
  # 1.11+ for write-only arguments (secret_string_wo); checked against 1.17.x, November 2026.
  required_version = ">= 1.11"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0" # 6.x is the current major (6.71 in late October 2026); 7.0 will not be picked up silently
    }
  }
}

provider "aws" {
  region = var.region

  # Every resource gets these tags: find (and pay for) the lab's resources by tag.
  default_tags {
    tags = {
      Project   = var.project
      Project   = "F2"
      ManagedBy = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}
