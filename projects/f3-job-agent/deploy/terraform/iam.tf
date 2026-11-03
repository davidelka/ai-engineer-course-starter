# Three roles, three jobs:
#   execution role  the ECS agent: pull the image, write logs, read the two SSM parameters
#   task role       the agent's code: read/write ONLY its own S3 prefixes
#   scheduler role  EventBridge Scheduler: run THIS task definition and pass THOSE two roles

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
    resources = [aws_ecr_repository.agent.arn]
  }
  statement {
    sid       = "EcrLogin"
    actions   = ["ecr:GetAuthorizationToken"] # no resource-level permissions exist for this action
    resources = ["*"]
  }
  statement {
    sid       = "WriteThisLogGroupOnly"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.agent.arn}:*"]
  }
  statement {
    sid       = "ReadTheTwoParameters"
    actions   = ["ssm:GetParameters"] # what ECS calls to inject `secrets` from Parameter Store
    resources = [aws_ssm_parameter.anthropic.arn, aws_ssm_parameter.airtable.arn]
  }
}

resource "aws_iam_role_policy" "execution" {
  name   = "least-privilege"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.execution.json
}

# ---------------------------------------------------------------- task role
resource "aws_iam_role" "task" {
  name               = "${var.project}-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_trust.json
}

data "aws_iam_policy_document" "task" {
  statement {
    sid       = "StateReadWrite"
    actions   = ["s3:GetObject", "s3:PutObject"] # If-Match needs both (S3 conditional writes)
    resources = ["${aws_s3_bucket.data.arn}/state/*", "${aws_s3_bucket.data.arn}/outbox/*"]
  }
  statement {
    sid       = "InboxRead"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.data.arn}/inbox/*"]
  }
  statement {
    sid       = "ListOwnPrefixes"
    actions   = ["s3:ListBucket"] # without it a missing key is AccessDenied instead of NoSuchKey
    resources = [aws_s3_bucket.data.arn]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["state/*", "inbox/*", "outbox/*"]
    }
  }
}

resource "aws_iam_role_policy" "task" {
  name   = "own-prefixes-only"
  role   = aws_iam_role.task.id
  policy = data.aws_iam_policy_document.task.json
}

# ---------------------------------------------------------------- scheduler role
data "aws_iam_policy_document" "scheduler_trust" {
  statement {
    sid     = "SchedulerAssume"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_iam_role" "scheduler" {
  name               = "${var.project}-scheduler"
  assume_role_policy = data.aws_iam_policy_document.scheduler_trust.json
}

data "aws_iam_policy_document" "scheduler" {
  statement {
    sid     = "RunThisTaskDefinition"
    actions = ["ecs:RunTask"]
    # any revision of this family: a new image tag creates a new revision
    resources = ["${aws_ecs_task_definition.agent.arn_without_revision}:*"]
    condition {
      test     = "ArnEquals"
      variable = "ecs:cluster"
      values   = [aws_ecs_cluster.main.arn]
    }
  }
  statement {
    sid       = "PassOnlyTheseRoles"
    actions   = ["iam:PassRole"]
    resources = [aws_iam_role.execution.arn, aws_iam_role.task.arn]
    condition {
      test     = "StringLike"
      variable = "iam:PassedToService"
      values   = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "scheduler" {
  name   = "run-agent-task"
  role   = aws_iam_role.scheduler.id
  policy = data.aws_iam_policy_document.scheduler.json
}
