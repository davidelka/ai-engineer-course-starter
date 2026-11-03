# EFS: the SQLite file survives task restarts and deployments.
#
# Why EFS and not the task's disk: Fargate's ephemeral storage is deleted with the task, and
# every deployment replaces the task. Why not RDS: for one writer and a few classes, a managed
# Postgres (about $15/month for the smallest) is more than the pilot needs. When the app needs
# more than ONE task, SQLite on EFS stops being safe (file locking over NFS); that is the moment
# to move to Postgres, not before.
resource "aws_efs_file_system" "data" {
  creation_token   = "${var.project}-data"
  encrypted        = true # at rest, with the AWS-managed key: student data
  performance_mode = "generalPurpose"
  throughput_mode  = "elastic"

  lifecycle_policy {
    transition_to_ia = "AFTER_30_DAYS"
  }
}

resource "aws_efs_mount_target" "data" {
  for_each        = toset(data.aws_subnets.public.ids)
  file_system_id  = aws_efs_file_system.data.id
  subnet_id       = each.value
  security_groups = [aws_security_group.efs.id]
}

# The app sees only /tutor on the file system, as UID 10001 (the image's non-root user).
resource "aws_efs_access_point" "data" {
  file_system_id = aws_efs_file_system.data.id

  posix_user {
    uid = 10001
    gid = 10001
  }

  root_directory {
    path = "/tutor"
    creation_info {
      owner_uid   = 10001
      owner_gid   = 10001
      permissions = "0750"
    }
  }
}
