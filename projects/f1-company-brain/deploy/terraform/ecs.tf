# One Fargate task running `python -m cbrain serve`, the production configuration:
#   MODE=live, LLM_PATH=gateway (every model call through the in-process gatewaykit: budgets, policy by
#   data classification, audit), guards on, no demo keys, SQLITE_EXCLUSIVE=1 (state on EFS, see efs.tf).
# Differences from lesson 27: an EFS volume, two secrets (one injected per JSON key), no autoscaling and a
# stop-then-start deployment (one writer for SQLite), a longer start period for the first indexing.

resource "aws_ecs_cluster" "main" {
  name = var.project

  setting {
    name  = "containerInsights"
    value = "disabled"
  }
}

locals {
  brain_container = {
    name      = "brain"
    image     = "${aws_ecr_repository.brain.repository_url}:${var.image_tag}"
    essential = true
    command   = ["serve"]

    portMappings = [{ containerPort = var.container_port, protocol = "tcp" }]

    environment = [
      { name = "MODE", value = var.mode },
      { name = "LLM_PATH", value = "gateway" },
      { name = "GUARDS", value = "on" },
      { name = "STATE_DIR", value = "/data/state" },
      { name = "SQLITE_EXCLUSIVE", value = "1" },
      { name = "ROUTER_LLM", value = "auto" },
      { name = "APP_VERSION", value = var.image_tag },
    ]

    # valueFrom "<secret-arn>:<json-key>::" picks one key out of a JSON secret.
    secrets = [
      { name = "ANTHROPIC_API_KEY", valueFrom = "${aws_secretsmanager_secret.provider_keys.arn}:ANTHROPIC_API_KEY::" },
      { name = "OPENAI_API_KEY", valueFrom = "${aws_secretsmanager_secret.provider_keys.arn}:OPENAI_API_KEY::" },
      { name = "BRAIN_API_KEYS", valueFrom = aws_secretsmanager_secret.brain_keys.arn },
    ]

    readonlyRootFilesystem = true

    mountPoints = [{ sourceVolume = "state", containerPath = "/data", readOnly = false }]

    healthCheck = {
      command     = ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:${var.container_port}/healthz', timeout=2)"]
      interval    = 15
      timeout     = 5
      retries     = 3
      startPeriod = 120
    }

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.brain.name
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "brain"
        "mode"                  = "non-blocking"
        "max-buffer-size"       = "25m"
      }
    }

    stopTimeout = 60 # finish in-flight answers; the graph state is checkpointed after every step anyway
  }
}

resource "aws_ecs_task_definition" "brain" {
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

  # /tmp for libraries that need scratch space under a read-only root filesystem
  ephemeral_storage {
    size_in_gib = 21
  }

  volume {
    name = "state"
    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.state.id
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = aws_efs_access_point.state.id
        iam             = "ENABLED"
      }
    }
  }

  container_definitions = jsonencode([local.brain_container])
}

resource "aws_ecs_service" "brain" {
  name            = var.project
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.brain.arn
  desired_count   = 1 # ONE writer for the SQLite files on EFS (ADR-0003). More tasks = Postgres first.
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = data.aws_subnets.public.ids
    security_groups  = [aws_security_group.task.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.brain.arn
    container_name   = "brain"
    container_port   = var.container_port
  }

  # Stop the old task BEFORE starting the new one: never two processes on the same SQLite files.
  # The price is about a minute of downtime per deployment, which an internal tool can take.
  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 100
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  health_check_grace_period_seconds = 180

  propagate_tags = "SERVICE"
  depends_on     = [aws_lb_listener.http, aws_iam_role_policy.execution, aws_efs_mount_target.state]
}
