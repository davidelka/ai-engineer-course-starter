# Two roles, two different jobs. Mixing them is the most common ECS IAM mistake.
#
#   EXECUTION role: used by the ECS agent BEFORE and AROUND your container. It pulls the
#   image from ECR, creates the log stream, reads the secret and injects it as an env var.
#   Your code never gets these credentials.
#
#   TASK role: the identity of YOUR CODE. Whatever the app does with the AWS SDK (read a
#   bucket of Acme documents, write to DynamoDB) is allowed here, and only here. The
#   credentials are served to the container at runtime.
#
# Every policy is written as data "aws_iam_policy_document" (not inline JSON) so that
# Terraform validates it and checks.py can lint it.

data "aws_iam_policy_document" "ecs_tasks_trust" {
  statement {
    sid     = "EcsTasksAssume"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }

    # Confused-deputy protection: only ECS acting for THIS account may assume the role.
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["arn:aws:ecs:${var.region}:${data.aws_caller_identity.current.account_id}:*"]
    }
  }
}

# ---------------------------------------------------------------- execution role
resource "aws_iam_role" "execution" {
  name               = "${var.project}-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_trust.json
}

data "aws_iam_policy_document" "execution" {
  statement {
    sid       = "PullThisRepositoryOnly"
    actions   = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"]
    resources = [aws_ecr_repository.api.arn]
  }

  # GetAuthorizationToken does not support resource-level permissions: "*" is the only
  # valid resource. That is an AWS limitation, not laziness (checks.py knows this).
  statement {
    sid       = "EcrLogin"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid       = "WriteThisLogGroupOnly"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.api.arn}:*"]
  }

  # The ONLY secret this service may read. With a customer-managed KMS key you would
  # also need kms:Decrypt on that key; the default aws/secretsmanager key needs nothing.
  statement {
    sid       = "ReadTheThreeSecretsOnly"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.anthropic.arn, aws_secretsmanager_secret.openai.arn, aws_secretsmanager_secret.admin_token.arn]
  }
}

resource "aws_iam_role_policy" "execution" {
  name   = "least-privilege"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.execution.json
}

# ---------------------------------------------------------------- task role
# The app's own AWS permissions: mount and write ONE EFS access point (the SQLite file).
# It calls Anthropic and OpenAI over HTTPS with keys, not AWS APIs.
resource "aws_iam_role" "task" {
  name               = "${var.project}-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_trust.json
}

data "aws_iam_policy_document" "task" {
  statement {
    sid       = "MountTheDataAccessPointOnly"
    actions   = ["elasticfilesystem:ClientMount", "elasticfilesystem:ClientWrite"]
    resources = [aws_efs_file_system.data.arn]
    condition {
      test     = "StringEquals"
      variable = "elasticfilesystem:AccessPointArn"
      values   = [aws_efs_access_point.data.arn]
    }
  }
}

resource "aws_iam_role_policy" "task" {
  name   = "efs-data"
  role   = aws_iam_role.task.id
  policy = data.aws_iam_policy_document.task.json
}
