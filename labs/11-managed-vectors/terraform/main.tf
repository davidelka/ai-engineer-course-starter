# Lesson 11, exercise 8 (optional): an Amazon S3 Vectors bucket + index for Company Brain.
#   cd labs/11-managed-vectors/terraform
#   terraform init && terraform plan -var bucket_name=acme-brain-<you>
#   terraform apply -var bucket_name=acme-brain-<you>
#   ... python labs/11-managed-vectors/s3vectors_demo.py --bucket acme-brain-<you> --region eu-central-1
#   terraform destroy -var bucket_name=acme-brain-<you>        # TEARDOWN: storage billing stops
# Resources aws_s3vectors_vector_bucket / aws_s3vectors_index are in the AWS provider 6.x
# (checked against the provider docs, November 2026). Every index argument forces a
# replacement: changing dimension or metric = a new, empty index (re-ingest).

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.0"
    }
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = { project = "company-brain", lesson = "11", owner = "david" }
  }
}

variable "region" {
  type        = string
  default     = "eu-central-1"          # S3 Vectors regions: see the lesson; il-central-1 was not listed
  description = "AWS region with S3 Vectors"
}

variable "bucket_name" {
  type        = string
  description = "Vector bucket name (lowercase, unique in the account/region)"
}

variable "dimension" {
  type    = number
  default = 384                          # multilingual-e5-small; 1536 for text-embedding-3-small
}

resource "aws_s3vectors_vector_bucket" "brain" {
  vector_bucket_name = var.bucket_name
  force_destroy      = true             # lab only: destroy deletes indexes and vectors too
  # encryption defaults to SSE-S3 (AES256); use aws:kms + kms_key_arn for a customer key
}

resource "aws_s3vectors_index" "chunks" {
  vector_bucket_name = aws_s3vectors_vector_bucket.brain.vector_bucket_name
  index_name         = "acme-chunks"
  data_type          = "float32"
  dimension          = var.dimension
  distance_metric    = "cosine"

  metadata_configuration {
    # the chunk JSON (text, offsets, title) is returned with hits but never filtered on:
    # non-filterable keys do not count toward the 2 KB filterable limit or query pricing
    non_filterable_metadata_keys = ["chunk"]
  }
}

# Least privilege for the Company Brain API: query + write this one index, nothing else.
data "aws_iam_policy_document" "brain_vectors" {
  statement {
    actions   = ["s3vectors:QueryVectors", "s3vectors:GetVectors", "s3vectors:PutVectors",
                 "s3vectors:DeleteVectors", "s3vectors:ListVectors"]
    resources = [aws_s3vectors_index.chunks.index_arn]
  }
}

resource "aws_iam_policy" "brain_vectors" {
  name   = "${var.bucket_name}-chunks-rw"
  policy = data.aws_iam_policy_document.brain_vectors.json
}

output "index_arn" {
  value = aws_s3vectors_index.chunks.index_arn
}

output "policy_arn" {
  value = aws_iam_policy.brain_vectors.arn
}
