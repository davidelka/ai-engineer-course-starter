# Two secrets (the values go in with the AWS CLI, never through Terraform, so they never reach the state):
#   <project>/provider-keys   JSON {"ANTHROPIC_API_KEY": "...", "OPENAI_API_KEY": "..."}
#   <project>/brain-api-keys  JSON {"dana": "<key>", ...}  from `python -m cbrain keys`
# ECS injects them as environment variables at task start (the execution role reads them). One JSON
# secret with two keys costs $0.40/month, the same as one key: provider keys share a secret.

resource "aws_secretsmanager_secret" "provider_keys" {
  name                    = "${var.project}/provider-keys"
  description             = "Model provider API keys for Company Brain (JSON: ANTHROPIC_API_KEY, OPENAI_API_KEY)"
  recovery_window_in_days = 0 # course stack: delete at once on destroy (the default keeps billing for 30 days)
}

resource "aws_secretsmanager_secret" "brain_keys" {
  name                    = "${var.project}/brain-api-keys"
  description             = "Company Brain user API keys (JSON user_id -> key); the service keeps only hashes"
  recovery_window_in_days = 0
}

resource "aws_cloudwatch_log_group" "brain" {
  name              = "/ecs/${var.project}"
  retention_in_days = var.log_retention_days
}

resource "aws_ecr_repository" "brain" {
  name                 = var.project
  image_tag_mutability = "IMMUTABLE"
  force_delete         = true # course stack: destroy deletes the images too

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "brain" {
  repository = aws_ecr_repository.brain.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the last 5 images"
      selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 5 }
      action       = { type = "expire" }
    }]
  })
}

# An alarm on the brain's own failure signal: unhealthy targets behind the ALB.
resource "aws_cloudwatch_metric_alarm" "unhealthy" {
  alarm_name          = "${var.project}-unhealthy-target"
  alarm_description   = "The brain task fails /readyz (index, state or keys missing)"
  namespace           = "AWS/ApplicationELB"
  metric_name         = "UnHealthyHostCount"
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 5
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  dimensions = {
    LoadBalancer = aws_lb.brain.arn_suffix
    TargetGroup  = aws_lb_target_group.brain.arn_suffix
  }
}
