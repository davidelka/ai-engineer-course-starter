output "url" {
  description = "The API and demo page, through the load balancer"
  value       = var.certificate_arn == "" ? "http://${aws_lb.api.dns_name}" : "https://${aws_lb.api.dns_name} (point your domain's CNAME here)"
}

output "ecr_repository_url" {
  value = aws_ecr_repository.api.repository_url
}

output "secret_names" {
  description = "Put the three values with the AWS CLI (README, milestone 10)"
  value       = [aws_secretsmanager_secret.anthropic.name, aws_secretsmanager_secret.openai.name, aws_secretsmanager_secret.admin_token.name]
}

output "log_group" {
  value = aws_cloudwatch_log_group.api.name
}

output "push_commands" {
  value = <<-EOT
    aws ecr get-login-password --region ${var.region} | docker login --username AWS --password-stdin ${split("/", aws_ecr_repository.api.repository_url)[0]}
    docker tag hebrew-tutor:dev ${aws_ecr_repository.api.repository_url}:${var.image_tag}
    docker push ${aws_ecr_repository.api.repository_url}:${var.image_tag}
  EOT
}
