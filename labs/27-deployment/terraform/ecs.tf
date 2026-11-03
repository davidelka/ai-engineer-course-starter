# ECS on Fargate: AWS runs the containers; there are no servers to patch.

resource "aws_ecs_cluster" "main" {
  name = var.project

  # Container Insights adds per-task CPU/memory/network metrics, billed as custom
  # metrics. Off for the lab; turn it on ("enhanced") when you operate this for real.
  setting {
    name  = "containerInsights"
    value = "disabled"
  }
}

locals {
  # The container definition, as HCL instead of a JSON string: Terraform checks it,
  # and checks.py can read it. jsonencode() turns it into what the ECS API expects.
  api_container = {
    name      = "api"
    image     = "${aws_ecr_repository.api.repository_url}:${var.image_tag}"
    essential = true

    portMappings = [{ containerPort = var.container_port, protocol = "tcp" }]

    # Plain configuration: visible in the console and in the task definition. Fine for
    # anything that is not a secret.
    environment = [
      { name = "LLM_MODEL", value = var.llm_model },
      { name = "MAX_TOKENS", value = "400" },
      { name = "APP_VERSION", value = var.image_tag },
    ]

    # Secrets: the task definition holds only the ARN. At task start, the ECS agent
    # (using the EXECUTION role) reads the value from Secrets Manager and sets the env
    # var inside the container. Rotating the secret needs a new deployment:
    #   aws ecs update-service --cluster company-brain --service company-brain-api --force-new-deployment
    secrets = [
      { name = "ANTHROPIC_API_KEY", valueFrom = aws_secretsmanager_secret.anthropic.arn },
    ]

    readonlyRootFilesystem = true # the app writes nothing to disk; an attacker cannot either

    # Liveness. ECS ignores the HEALTHCHECK in the image, so it is repeated here.
    # An unhealthy container is replaced by ECS.
    healthCheck = {
      command     = ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:${var.container_port}/healthz', timeout=2)"]
      interval    = 15
      timeout     = 5
      retries     = 3
      startPeriod = 15
    }

    # stdout/stderr -> CloudWatch Logs. non-blocking: if CloudWatch is slow, the app
    # does not freeze waiting for the log driver (some lines may drop instead).
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

    stopTimeout = 30 # seconds between SIGTERM and SIGKILL: time to finish in-flight answers
  }
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${var.project}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc" # every task gets its own network interface and IP
  cpu                      = var.cpu
  memory                   = var.memory

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = var.cpu_architecture
  }

  execution_role_arn = aws_iam_role.execution.arn # the ECS agent: pull, logs, secrets
  task_role_arn      = aws_iam_role.task.arn      # your code

  container_definitions = jsonencode([local.api_container])
}

resource "aws_ecs_service" "api" {
  name            = "${var.project}-api"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = data.aws_subnets.public.ids
    security_groups  = [aws_security_group.task.id]
    assign_public_ip = true # needed to reach ECR and the internet without a NAT gateway (see network.tf)
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = var.container_port
  }

  # Rolling deployment: start new tasks first (up to 200%), stop old ones when the new
  # ones are healthy. If new tasks keep failing, roll back to the last good revision.
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  health_check_grace_period_seconds = 30

  propagate_tags = "SERVICE"

  lifecycle {
    ignore_changes = [desired_count] # autoscaling owns the count after creation
  }

  depends_on = [aws_lb_listener.http, aws_iam_role_policy.execution]
}

# ---------------------------------------------------------------- autoscaling
# Scale on REQUESTS per task, not CPU. An LLM service spends most of its time waiting
# for the model API: CPU stays low while the task is already saturated with open
# requests, so CPU-based scaling reacts too late.
resource "aws_appautoscaling_target" "api" {
  service_namespace  = "ecs"
  scalable_dimension = "ecs:service:DesiredCount"
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.api.name}"
  min_capacity       = var.min_count
  max_capacity       = var.max_count
}

resource "aws_appautoscaling_policy" "requests" {
  name               = "${var.project}-requests-per-task"
  policy_type        = "TargetTrackingScaling"
  service_namespace  = aws_appautoscaling_target.api.service_namespace
  scalable_dimension = aws_appautoscaling_target.api.scalable_dimension
  resource_id        = aws_appautoscaling_target.api.resource_id

  target_tracking_scaling_policy_configuration {
    target_value       = var.requests_per_task_target
    scale_out_cooldown = 60
    scale_in_cooldown  = 180

    predefined_metric_specification {
      predefined_metric_type = "ALBRequestCountPerTarget"
      resource_label         = "${aws_lb.api.arn_suffix}/${aws_lb_target_group.api.arn_suffix}"
    }
  }
}
