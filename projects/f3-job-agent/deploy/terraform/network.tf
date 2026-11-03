# Default VPC, public subnets, a public IP on the task (no NAT gateway: about $33/month saved).
# The task accepts NO inbound traffic at all: it only calls out (S3, SSM, ECR, logs, Anthropic).

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "public" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
  filter {
    name   = "default-for-az"
    values = ["true"]
  }
}

resource "aws_security_group" "task" {
  name        = "${var.project}-task"
  description = "Job agent task: no inbound, HTTPS out only"
  vpc_id      = data.aws_vpc.default.id
}

resource "aws_vpc_security_group_egress_rule" "task_https" {
  security_group_id = aws_security_group.task.id
  description       = "HTTPS out: S3, SSM, ECR, CloudWatch Logs, api.anthropic.com, api.airtable.com"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
}
