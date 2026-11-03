# ---------------------------------------------------------------- ECR
resource "aws_ecr_repository" "agent" {
  name                 = var.project
  image_tag_mutability = "IMMUTABLE"
  force_delete         = true # project demo: destroy removes images too

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "agent" {
  repository = aws_ecr_repository.agent.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the last 5 images"
      selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 5 }
      action       = { type = "expire" }
    }]
  })
}

# ---------------------------------------------------------------- S3: state, inbox, outbox
#   state/state.db        the SQLite file, written with If-Match (optimistic concurrency)
#   inbox/whatsapp/*.json exports pushed by the bridge on the owner's computer
#   outbox/<slot>.txt     digests, picked up by the sender on the owner's computer
# Versioning keeps old copies of the state: a bad run can be rolled back.
resource "aws_s3_bucket" "data" {
  bucket_prefix = "${var.project}-"
  force_destroy = true # project demo only
}

resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "data" {
  bucket                  = aws_s3_bucket.data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    id     = "expire-old-versions-and-old-files"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }

  rule {
    id     = "inbox-outbox-retention"
    status = "Enabled"
    filter {
      prefix = "outbox/"
    }
    expiration {
      days = 14
    }
  }
}

# ---------------------------------------------------------------- secrets: SSM Parameter Store
# Standard SecureString parameters have no monthly charge (Secrets Manager: $0.40 per secret).
# Terraform creates them with a placeholder and never manages the value afterwards:
#   aws ssm put-parameter --name /job-agent/anthropic-api-key --type SecureString --overwrite --value "$(read -rs v; echo $v)"
resource "aws_ssm_parameter" "anthropic" {
  name        = "/${var.project}/anthropic-api-key"
  description = "Anthropic API key for the job agent (set the value with the AWS CLI)"
  type        = "SecureString"
  value       = "CHANGE_ME"

  lifecycle {
    ignore_changes = [value] # the real value is put with the CLI and never enters the state
  }
}

resource "aws_ssm_parameter" "airtable" {
  name        = "/${var.project}/airtable-token"
  description = "Airtable personal access token, scope data.records:read (optional)"
  type        = "SecureString"
  value       = "CHANGE_ME"

  lifecycle {
    ignore_changes = [value]
  }
}

# ---------------------------------------------------------------- logs
resource "aws_cloudwatch_log_group" "agent" {
  name              = "/ecs/${var.project}"
  retention_in_days = var.log_retention_days
}
