output "ecr_repository_url" {
  value = aws_ecr_repository.agent.repository_url
}

output "bucket" {
  value = aws_s3_bucket.data.bucket
}

output "push_commands" {
  description = "Build and push the image (run from the repo root)."
  value       = <<-EOT
    aws ecr get-login-password --region ${var.region} | docker login --username AWS --password-stdin ${split("/", aws_ecr_repository.agent.repository_url)[0]}
    docker build -f projects/f3-job-agent/deploy/Dockerfile -t ${aws_ecr_repository.agent.repository_url}:${var.image_tag} .
    docker push ${aws_ecr_repository.agent.repository_url}:${var.image_tag}
  EOT
}

output "run_now" {
  description = "Start one run immediately (same network settings as the schedule)."
  value       = "aws ecs run-task --cluster ${aws_ecs_cluster.main.name} --launch-type FARGATE --task-definition ${aws_ecs_task_definition.agent.family} --network-configuration 'awsvpcConfiguration={subnets=[${join(",", data.aws_subnets.public.ids)}],securityGroups=[${aws_security_group.task.id}],assignPublicIp=ENABLED}' --overrides '{\"containerOverrides\":[{\"name\":\"agent\",\"command\":[\"run\",\"--slot\",\"auto\",\"--force\"]}]}'"
}

output "log_group" {
  value = aws_cloudwatch_log_group.agent.name
}

output "schedules" {
  value = { for k, s in aws_scheduler_schedule.slot : k => "${s.schedule_expression} ${s.schedule_expression_timezone}" }
}
