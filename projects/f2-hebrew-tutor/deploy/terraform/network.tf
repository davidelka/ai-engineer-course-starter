# Network: the account's DEFAULT VPC, two availability zones, public subnets.
#
# Why public subnets with a public IP on the task, and not private subnets?
# A task must reach ECR (to pull the image), Secrets Manager, CloudWatch Logs and the
# Anthropic API. From a private subnet that needs a NAT gateway (about $33/month plus
# $0.045/GB) or interface VPC endpoints (about $7.30/month EACH per AZ; four are needed:
# about $58/month for two AZs). For a lab, a public IP ($3.65/month) and a security group
# that accepts traffic ONLY from the load balancer is the honest trade-off. Production
# usually goes private + NAT. The cost estimator in the lesson shows all three.
#
# No default VPC (some accounts deleted it)? Create one: aws ec2 create-default-vpc

data "aws_vpc" "default" {
  default = true
}

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs = slice(data.aws_availability_zones.available.names, 0, 2) # an ALB needs at least two AZs
}

data "aws_subnets" "public" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
  filter {
    name   = "availability-zone"
    values = local.azs
  }
  filter {
    name   = "default-for-az"
    values = ["true"]
  }
}

# ---------------------------------------------------------------- security groups
# Two groups, chained: internet -> ALB (port 80) -> task (container port, from the ALB only).

resource "aws_security_group" "alb" {
  name        = "${var.project}-alb"
  description = "Load balancer: HTTP from allowed_cidr"
  vpc_id      = data.aws_vpc.default.id
}

resource "aws_vpc_security_group_ingress_rule" "alb_https" {
  count             = var.certificate_arn == "" ? 0 : 1
  security_group_id = aws_security_group.alb.id
  description       = "HTTPS from the allowed range"
  cidr_ipv4         = var.allowed_cidr
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
}

resource "aws_vpc_security_group_ingress_rule" "alb_http" {
  security_group_id = aws_security_group.alb.id
  description       = "HTTP from the allowed range"
  cidr_ipv4         = var.allowed_cidr
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
}

resource "aws_vpc_security_group_egress_rule" "alb_to_tasks" {
  security_group_id            = aws_security_group.alb.id
  description                  = "To the tasks on the container port"
  referenced_security_group_id = aws_security_group.task.id
  ip_protocol                  = "tcp"
  from_port                    = var.container_port
  to_port                      = var.container_port
}

resource "aws_security_group" "task" {
  name        = "${var.project}-task"
  description = "API tasks: container port from the ALB only"
  vpc_id      = data.aws_vpc.default.id
}

resource "aws_vpc_security_group_ingress_rule" "task_from_alb" {
  security_group_id            = aws_security_group.task.id
  description                  = "Container port, only from the load balancer"
  referenced_security_group_id = aws_security_group.alb.id
  ip_protocol                  = "tcp"
  from_port                    = var.container_port
  to_port                      = var.container_port
}

resource "aws_vpc_security_group_egress_rule" "task_https" {
  security_group_id = aws_security_group.task.id
  description       = "HTTPS out: ECR, Secrets Manager, CloudWatch Logs, api.anthropic.com, api.openai.com"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
}

# NFS from the task to EFS (the SQLite file). Only the task's security group may mount it.
resource "aws_vpc_security_group_egress_rule" "task_nfs" {
  security_group_id            = aws_security_group.task.id
  description                  = "NFS to EFS"
  referenced_security_group_id = aws_security_group.efs.id
  ip_protocol                  = "tcp"
  from_port                    = 2049
  to_port                      = 2049
}

resource "aws_security_group" "efs" {
  name        = "${var.project}-efs"
  description = "EFS: NFS from the API task only"
  vpc_id      = data.aws_vpc.default.id
}

resource "aws_vpc_security_group_ingress_rule" "efs_from_task" {
  security_group_id            = aws_security_group.efs.id
  description                  = "NFS from the API task"
  referenced_security_group_id = aws_security_group.task.id
  ip_protocol                  = "tcp"
  from_port                    = 2049
  to_port                      = 2049
}
