# ---------------------------------------------------------------- ECR: the image registry
resource "aws_ecr_repository" "api" {
  name                 = "${var.project}-api"
  image_tag_mutability = "IMMUTABLE" # a tag always means the same image: v1 cannot be overwritten
  force_delete         = true        # lab only: lets `terraform destroy` delete a repo that has images

  image_scanning_configuration {
    scan_on_push = true # basic scanning (free): CVEs of OS packages, visible in the console
  }
}

resource "aws_ecr_lifecycle_policy" "api" {
  repository = aws_ecr_repository.api.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the last 5 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 5
      }
      action = { type = "expire" }
    }]
  })
}

# ---------------------------------------------------------------- Secrets Manager: the API key
# Terraform creates the secret (the container), NOT its value. If the value were written
# here with secret_string, it would sit in plain text in terraform.tfstate.
# Put the value with the AWS CLI (README, exercise 8), or with Terraform >= 1.11:
#   resource "aws_secretsmanager_secret_version" "anthropic" {
#     secret_id                = aws_secretsmanager_secret.anthropic.id
#     secret_string_wo         = var.anthropic_api_key   # write-only: never stored in state
#     secret_string_wo_version = 1                        # bump to push a new value
#   }
resource "aws_secretsmanager_secret" "anthropic" {
  name        = "${var.project}/anthropic-api-key"
  description = "Anthropic API key for the Company Brain API (lesson 27)"

  # Lab only: delete immediately on destroy. The default (30 days) keeps the secret,
  # and keeps billing $0.40/month for it, and blocks re-creating the same name.
  recovery_window_in_days = 0
}

# ---------------------------------------------------------------- CloudWatch Logs
resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${var.project}-api"
  retention_in_days = var.log_retention_days # without this, logs are kept and billed forever
}
