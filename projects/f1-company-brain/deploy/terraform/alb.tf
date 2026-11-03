# The public entry point, as in lesson 27. Differences: idle_timeout 300 s, because /ask streams SSE and
# an access request's stream waits for the workflow; stickiness is not needed (one task).

resource "aws_lb" "brain" {
  name                       = "${var.project}-alb"
  load_balancer_type         = "application"
  internal                   = false
  security_groups            = [aws_security_group.alb.id]
  subnets                    = data.aws_subnets.public.ids
  idle_timeout               = 300
  drop_invalid_header_fields = true
}

resource "aws_lb_target_group" "brain" {
  name        = "${var.project}-tg"
  port        = var.container_port
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = data.aws_vpc.default.id

  # /readyz: index built, state reachable, users and keys loaded. The first start with the e5 image
  # embeds the corpus (about a minute), so the task is alive (/healthz) before it is ready.
  health_check {
    path                = "/readyz"
    matcher             = "200"
    interval            = 15
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 4
  }

  deregistration_delay = 30
}

# HTTP only, like lesson 27, to keep the course free of a domain and a certificate. The API keys travel
# in a header: restrict allowed_cidr to your IP, and add ACM + a 443 listener before real users.
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.brain.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.brain.arn
  }
}
