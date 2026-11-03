# EventBridge Scheduler: one schedule per slot, cron in Asia/Jerusalem (DST handled by AWS).
# 08:30 and 15:00/21:00 have different minutes, so one cron expression cannot cover all three.
# The same slots are defined in jobagent/schedule.py (SLOTS); `python -m jobagent schedule --show`
# prints these expressions, and tests/test_f3_job_agent.py checks that both lists agree.

resource "aws_scheduler_schedule_group" "agent" {
  name = var.project
}

resource "aws_scheduler_schedule" "slot" {
  for_each = var.slots

  name       = "${var.project}-${each.key}"
  group_name = aws_scheduler_schedule_group.agent.name
  state      = var.schedules_enabled ? "ENABLED" : "DISABLED"

  schedule_expression          = "cron(${each.value.minute} ${each.value.hour} * * ? *)"
  schedule_expression_timezone = var.schedule_timezone

  flexible_time_window {
    mode = "OFF" # run on time: the digest is expected at 08:30, not "around" it
  }

  target {
    arn      = aws_ecs_cluster.main.arn
    role_arn = aws_iam_role.scheduler.arn

    ecs_parameters {
      task_definition_arn = aws_ecs_task_definition.agent.arn
      launch_type         = "FARGATE"
      task_count          = 1

      network_configuration {
        subnets          = data.aws_subnets.public.ids
        security_groups  = [aws_security_group.task.id]
        assign_public_ip = true
      }
    }

    # A failed RunTask (capacity, throttling) is retried; a run that started and failed is not:
    # the next slot picks up its posts, and the slot key makes a duplicate start harmless.
    retry_policy {
      maximum_event_age_in_seconds = 1800
      maximum_retry_attempts       = 3
    }
  }
}
