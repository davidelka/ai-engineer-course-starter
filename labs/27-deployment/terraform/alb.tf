# Application Load Balancer: the public entry point. Billed every hour it exists
# ($0.0225/hour + capacity units), even with zero traffic.

resource "aws_lb" "api" {
  name               = "${var.project}-alb"
  load_balancer_type = "application"
  internal           = false
  security_groups    = [aws_security_group.alb.id]
  subnets            = data.aws_subnets.public.ids

  # LLM answers can take a while, and streaming keeps the connection open between
  # chunks. The default idle timeout is 60 seconds.
  idle_timeout = 120

  drop_invalid_header_fields = true
}

resource "aws_lb_target_group" "api" {
  name        = "${var.project}-tg"
  port        = var.container_port
  protocol    = "HTTP"
  target_type = "ip" # Fargate tasks register by IP (awsvpc networking)
  vpc_id      = data.aws_vpc.default.id

  # The ALB asks "can you take traffic?" -> readiness. ECS asks "are you alive?" -> /healthz
  # in the task definition. A task that is alive but not ready gets no traffic and is NOT killed.
  health_check {
    path                = "/readyz"
    matcher             = "200"
    interval            = 15
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  # How long a task that is being replaced keeps serving requests already in flight.
  # The default is 300 seconds, which makes every deployment and destroy slow.
  deregistration_delay = 30
}

# HTTP only, to keep the lab free of a domain and a certificate. Real traffic needs
# HTTPS: an ACM certificate (free) for a domain you own, a listener on 443, and a
# redirect from 80. Until then, do not send anything secret to this endpoint.
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}
