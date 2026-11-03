resource "aws_ecs_cluster" "main" {
  name = var.project

  setting {
    name  = "containerInsights"
    value = "disabled"
  }
}

locals {
  agent_container = {
    name      = "agent"
    image     = "${aws_ecr_repository.agent.repository_url}:${var.image_tag}"
    essential = true
    # ENTRYPOINT is ["python", "-m", "jobagent"]: one run for the slot that is due, then exit.
    command = ["run", "--slot", "auto"]

    environment = [
      { name = "EXTRACTOR", value = var.extractor },
      { name = "LLM_MODEL", value = var.llm_model },
      { name = "DELIVERY", value = "file" },
      { name = "DRAFTS", value = "none" }, # Gmail drafts stay on the owner's computer (OAuth token)
      { name = "STATE_S3_BUCKET", value = aws_s3_bucket.data.bucket },
      { name = "STATE_S3_OBJECT", value = "state/state.db" },
      { name = "INBOX_S3_PREFIX", value = "inbox/" },
      { name = "OUTBOX_S3_PREFIX", value = "outbox/" },
      { name = "WHATSAPP_DIR", value = "/data/inbox/whatsapp" },
      { name = "AIRTABLE_FIXTURE", value = "/data/inbox/airtable/new_jobs.json" },
      { name = "PREFS_PATH", value = "/data/preferences.yaml" },
      { name = "APP_VERSION", value = var.image_tag },
    ]

    # Injected by the ECS agent (execution role) from Parameter Store when the task starts.
    secrets = [
      { name = "ANTHROPIC_API_KEY", valueFrom = aws_ssm_parameter.anthropic.arn },
      { name = "AIRTABLE_TOKEN", valueFrom = aws_ssm_parameter.airtable.arn },
    ]

    # /data is the task's ephemeral storage (20 GiB included with Fargate); the root fs stays read-only.
    readonlyRootFilesystem = true
    mountPoints            = [{ sourceVolume = "data", containerPath = "/data", readOnly = false }]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.agent.name
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "run"
      }
    }
    stopTimeout = 30
  }
}

resource "aws_ecs_task_definition" "agent" {
  family                   = var.project
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  execution_role_arn = aws_iam_role.execution.arn
  task_role_arn      = aws_iam_role.task.arn

  volume {
    name = "data" # a bind volume on the task's ephemeral storage
  }

  container_definitions = jsonencode([local.agent_container])
}
