output "url" {
  description = "The API, through the load balancer"
  value       = "http://${aws_lb.api.dns_name}"
}

output "ecr_repository_url" {
  value = aws_ecr_repository.api.repository_url
}

output "secret_name" {
  description = "Put the key value here with the AWS CLI (README, exercise 8)"
  value       = aws_secretsmanager_secret.anthropic.name
}

output "log_group" {
  description = "aws logs tail <this> --follow"
  value       = aws_cloudwatch_log_group.api.name
}

output "cluster" {
  value = aws_ecs_cluster.main.name
}

output "service" {
  value = aws_ecs_service.api.name
}

output "push_commands" {
  description = "Log in to ECR, tag, push"
  value       = <<-EOT
    aws ecr get-login-password --region ${var.region} | docker login --username AWS --password-stdin ${split("/", aws_ecr_repository.api.repository_url)[0]}
    docker tag company-brain-api:dev ${aws_ecr_repository.api.repository_url}:${var.image_tag}
    docker push ${aws_ecr_repository.api.repository_url}:${var.image_tag}
  EOT
}
