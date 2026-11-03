# A deliberately BAD ECS setup for exercise 6. Never apply it: it is here to be linted.
#   python labs/27-deployment/checks.py labs/27-deployment/fixtures/bad_task.tf
# (No terraform block: the provider is not pinned either.)

variable "anthropic_api_key" {
  type    = string
  default = "sk-ant-lab27-FAKE-default-00000000"
}

resource "aws_secretsmanager_secret_version" "anthropic" {
  secret_id     = "company-brain/anthropic-api-key"
  secret_string = var.anthropic_api_key
}

data "aws_iam_policy_document" "app" {
  statement {
    actions   = ["*"]
    resources = ["*"]
  }
}

resource "aws_iam_role" "app" {
  name               = "app"
  assume_role_policy = "{}"
}

resource "aws_cloudwatch_log_group" "api" {
  name = "/ecs/bad-api"
}

resource "aws_security_group" "task" {
  name = "bad-task"
  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

locals {
  container = {
    name  = "api"
    image = "company-brain-api:latest"
    environment = [
      { name = "ANTHROPIC_API_KEY", value = var.anthropic_api_key },
      { name = "LLM_MODEL", value = "anthropic:claude-haiku-5-5" },
    ]
  }
}

resource "aws_ecs_task_definition" "api" {
  family                = "bad-api"
  execution_role_arn    = aws_iam_role.app.arn
  task_role_arn         = aws_iam_role.app.arn
  container_definitions = jsonencode([local.container])
}
