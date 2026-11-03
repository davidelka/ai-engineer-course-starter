# State on EFS: checkpoints.db (LangGraph), requests.db (requests, audit, outbox, threads), the document
# index, traces and the gateway audit. Why EFS and not RDS, and why ONE task: ADR-0003.
#
# The SQLite catch, and how the brain handles it: LangGraph's SqliteSaver turns on WAL mode, and WAL's
# shared-memory index does not work on a network file system (sqlite.org/wal.html). The task sets
# SQLITE_EXCLUSIVE=1, so checkpoints.db is opened in EXCLUSIVE locking mode before WAL is enabled and
# SQLite keeps the index in the process's heap instead ("Use of WAL Without Shared-Memory"). requests.db
# stays in the default rollback-journal mode and relies on NFSv4 byte-range locks, which EFS supports.
# Consequence: exactly one process may open the files. The service runs one task, and a deployment stops
# the old task before it starts the new one (deployment_minimum_healthy_percent = 0 in ecs.tf).

resource "aws_efs_file_system" "state" {
  creation_token   = "${var.project}-state"
  encrypted        = true            # at rest, with the AWS-managed key
  performance_mode = "generalPurpose"
  throughput_mode  = "elastic"       # pay per GB transferred; tiny for this workload

  lifecycle_policy {
    transition_to_ia = "AFTER_30_DAYS" # old trace files move to the cheaper class
  }

  tags = { Name = "${var.project}-state" }
}

resource "aws_efs_backup_policy" "state" {
  file_system_id = aws_efs_file_system.state.id
  backup_policy {
    status = "ENABLED" # AWS Backup daily: the requests and their audit trail are records
  }
}

resource "aws_efs_mount_target" "state" {
  for_each        = toset(data.aws_subnets.public.ids)
  file_system_id  = aws_efs_file_system.state.id
  subnet_id       = each.value
  security_groups = [aws_security_group.efs.id]
}

# The container runs as UID 10001 (the image's "app" user). The access point forces that identity and
# roots the task in /company-brain, so the task cannot see anything else on the file system.
resource "aws_efs_access_point" "state" {
  file_system_id = aws_efs_file_system.state.id

  posix_user {
    uid = 10001
    gid = 10001
  }

  root_directory {
    path = "/company-brain"
    creation_info {
      owner_uid   = 10001
      owner_gid   = 10001
      permissions = "0750"
    }
  }
}
