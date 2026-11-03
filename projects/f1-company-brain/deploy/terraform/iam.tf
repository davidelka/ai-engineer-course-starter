# Two roles, as in lesson 27. The execution role (the ECS agent) pulls the image, writes logs and reads
# the two secrets. The task role (the brain's code) may mount and write ITS access point on ITS file
# system, and nothing else: the brain calls the model providers over HTTPS, not AWS APIs.

data "aws_iam_policy_document" "ecs_tasks_trust" {
  statement {
    sid     = "EcsTasksAssume"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }

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

resource "aws_iam_role" "execution" {
  name               = "${var.project}-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_trust.json
}

data "aws_iam_policy_document" "execution" {
  statement {
    sid       = "PullThisRepositoryOnly"
    actions   = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"]
    resources = [aws_ecr_repository.brain.arn]
  }

  statement {
    sid       = "EcrLogin" # GetAuthorizationToken has no resource-level permissions: "*" is the only option
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid       = "WriteThisLogGroupOnly"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.brain.arn}:*"]
  }

  statement {
    sid       = "ReadTheTwoSecretsOnly"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.provider_keys.arn, aws_secretsmanager_secret.brain_keys.arn]
  }
}

resource "aws_iam_role_policy" "execution" {
  name   = "least-privilege"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.execution.json
}

resource "aws_iam_role" "task" {
  name               = "${var.project}-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_trust.json
}

data "aws_iam_policy_document" "task" {
  # EFS IAM authorization (efs_volume_configuration authorization_config iam = ENABLED): the mount is
  # allowed only for this role, only through this access point.
  statement {
    sid       = "MountStateThroughTheAccessPoint"
    actions   = ["elasticfilesystem:ClientMount", "elasticfilesystem:ClientWrite"]
    resources = [aws_efs_file_system.state.arn]

    condition {
      test     = "StringEquals"
      variable = "elasticfilesystem:AccessPointArn"
      values   = [aws_efs_access_point.state.arn]
    }
  }
}

resource "aws_iam_role_policy" "task" {
  name   = "efs-state-only"
  role   = aws_iam_role.task.id
  policy = data.aws_iam_policy_document.task.json
}
