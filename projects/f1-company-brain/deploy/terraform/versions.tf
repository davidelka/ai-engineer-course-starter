# Company Brain (final project F1) on AWS: one ECS Fargate task behind an ALB, state on EFS,
# secrets in Secrets Manager, logs in CloudWatch, a monthly budget. Based on lesson 27's Terraform
# (labs/27-deployment/terraform), with the differences explained at the top of each file.
#
#   terraform init
#   terraform plan  -out=tfplan        # ALWAYS read the plan before applying
#   terraform apply tfplan             # starts billing: about $1.70 per day (python -m cbrain cost)
#   terraform destroy                  # stops billing; then the teardown checklist in README.md
#
# State: local terraform.tfstate (git-ignored). It never contains a secret VALUE: Terraform creates
# the secrets, the values go in with the AWS CLI (README, milestone 12).

terraform {
  required_version = ">= 1.11"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0" # same constraint as lesson 27: 6.x, never a silent 7.0
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = var.project
      Course    = "ai-engineer"
      Unit      = "F1"
      ManagedBy = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}
