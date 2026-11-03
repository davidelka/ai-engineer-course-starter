output "url" {
  description = "Company Brain (UI at /, API docs at /docs)"
  value       = "http://${aws_lb.brain.dns_name}"
}

output "ecr_repository_url" {
  value = aws_ecr_repository.brain.repository_url
}

output "secrets" {
  description = "Put the values here with the AWS CLI (README, milestone 12): never through Terraform"
  value = {
    provider_keys = aws_secretsmanager_secret.provider_keys.name
    brain_keys    = aws_secretsmanager_secret.brain_keys.name
  }
}

output "log_group" {
  description = "aws logs tail <this> --follow"
  value       = aws_cloudwatch_log_group.brain.name
}

output "cluster" {
  value = aws_ecs_cluster.main.name
}

output "service" {
  value = aws_ecs_service.brain.name
}

output "efs_id" {
  value = aws_efs_file_system.state.id
}

output "push_commands" {
  description = "Build the e5 image for x86_64, log in to ECR, push"
  value       = <<-EOT
    docker build --platform linux/amd64 -f projects/f1-company-brain/deploy/Dockerfile --target runtime-e5 -t company-brain:${var.image_tag} .
    aws ecr get-login-password --region ${var.region} | docker login --username AWS --password-stdin ${split("/", aws_ecr_repository.brain.repository_url)[0]}
    docker tag company-brain:${var.image_tag} ${aws_ecr_repository.brain.repository_url}:${var.image_tag}
    docker push ${aws_ecr_repository.brain.repository_url}:${var.image_tag}
  EOT
}
