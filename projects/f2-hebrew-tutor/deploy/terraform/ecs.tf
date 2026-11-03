# ECS on Fargate, ONE task (SQLite on EFS has one writer; see efs.tf).

resource "aws_ecs_cluster" "main" {
  name = var.project

  setting {
    name  = "containerInsights"
    value = "disabled"
  }
}

locals {
  api_container = {
    name      = "api"
    image     = "${aws_ecr_repository.api.repository_url}:${var.image_tag}"
    essential = true
    command   = ["serve"]

    portMappings = [{ containerPort = var.container_port, protocol = "tcp" }]

    environment = [
      { name = "TUTOR", value = var.tutor },
      { name = "STT", value = var.stt },
      { name = "TTS", value = var.tts },
      { name = "LLM_MODEL", value = var.llm_model },
      { name = "RETENTION_DAYS", value = tostring(var.retention_days) },
      { name = "DB_PATH", value = "/data/tutor.db" },
      { name = "TRACES", value = "/data/traces.jsonl" },
      { name = "APP_VERSION", value = var.image_tag },
    ]

    # Only ARNs here; the ECS agent (execution role) injects the values at task start.
    secrets = [
      { name = "ANTHROPIC_API_KEY", valueFrom = aws_secretsmanager_secret.anthropic.arn },
      { name = "OPENAI_API_KEY", valueFrom = aws_secretsmanager_secret.openai.arn },
      { name = "ADMIN_TOKEN", valueFrom = aws_secretsmanager_secret.admin_token.arn },
    ]

    readonlyRootFilesystem = true
    mountPoints = [
      { sourceVolume = "data", containerPath = "/data", readOnly = false },
      { sourceVolume = "tmp", containerPath = "/tmp", readOnly = false }, # multipart uploads spool here
    ]

    healthCheck = {
      command     = ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:${var.container_port}/healthz', timeout=2)"]
      interval    = 15
      timeout     = 5
      retries     = 3
      startPeriod = 20
    }

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.api.name
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "api"
        "mode"                  = "non-blocking"
        "max-buffer-size"       = "25m"
      }
    }

    stopTimeout = 30
  }
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${var.project}-api"
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
    name = "data"
    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.data.id
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = aws_efs_access_point.data.id
        iam             = "ENABLED"
      }
    }
  }

  volume {
    name = "tmp" # task-local scratch space, deleted with the task
  }

  container_definitions = jsonencode([local.api_container])
}

resource "aws_ecs_service" "api" {
  name            = "${var.project}-api"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = data.aws_subnets.public.ids
    security_groups  = [aws_security_group.task.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = var.container_port
  }

  # Stop the old task BEFORE starting the new one: two tasks must never write the same SQLite
  # file. The price is a short outage (about a minute) on every deployment.
  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 100
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  health_check_grace_period_seconds = 30

  propagate_tags = "SERVICE"

  depends_on = [aws_lb_listener.http, aws_iam_role_policy.execution, aws_efs_mount_target.data]
}
