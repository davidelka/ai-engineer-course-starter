#!/usr/bin/env bash
# After `terraform destroy`: is anything of the lab still alive (and billing)?
#   bash labs/27-deployment/teardown_check.sh            # region us-east-1, project company-brain
#   REGION=il-central-1 PROJECT=company-brain bash labs/27-deployment/teardown_check.sh
# Read-only: it lists, it never deletes. Needs the AWS CLI v2 and credentials.
set -uo pipefail
REGION="${REGION:-us-east-1}"
PROJECT="${PROJECT:-company-brain}"
export AWS_PAGER=""

section() { printf '\n== %s\n' "$1"; }

section "Anything still tagged Project=$PROJECT (should be empty)"
aws resourcegroupstaggingapi get-resources --region "$REGION" \
  --tag-filters "Key=Project,Values=$PROJECT" \
  --query 'ResourceTagMappingList[].ResourceARN' --output text

section "Load balancers (billed hourly)"
aws elbv2 describe-load-balancers --region "$REGION" \
  --query "LoadBalancers[?contains(LoadBalancerName, '$PROJECT')].[LoadBalancerName,State.Code]" --output text

section "ECS clusters and running tasks"
aws ecs list-clusters --region "$REGION" --query 'clusterArns' --output text
aws ecs list-tasks --region "$REGION" --cluster "$PROJECT" --query 'taskArns' --output text 2>/dev/null || echo "(no cluster $PROJECT)"

section "NAT gateways (the lab creates none; anything here is from something else)"
aws ec2 describe-nat-gateways --region "$REGION" --filter Name=state,Values=available \
  --query 'NatGateways[].NatGatewayId' --output text

section "Public IPv4 addresses you own (Elastic IPs; each is billed hourly)"
aws ec2 describe-addresses --region "$REGION" --query 'Addresses[].[PublicIp,AssociationId]' --output text

section "Secrets (a secret scheduled for deletion is still listed with DeletedDate)"
aws secretsmanager list-secrets --region "$REGION" --include-planned-deletion \
  --query "SecretList[?starts_with(Name, '$PROJECT')].[Name,DeletedDate]" --output text

section "ECR repositories"
aws ecr describe-repositories --region "$REGION" \
  --query "repositories[?starts_with(repositoryName, '$PROJECT')].repositoryName" --output text 2>/dev/null

section "Log groups"
aws logs describe-log-groups --region "$REGION" --log-group-name-prefix "/ecs/$PROJECT" \
  --query 'logGroups[].logGroupName' --output text

section "Budget (this one SHOULD still exist)"
aws budgets describe-budgets --account-id "$(aws sts get-caller-identity --query Account --output text)" \
  --query 'Budgets[].[BudgetName,BudgetLimit.Amount]' --output text

printf '\nEmpty sections above = nothing left. Check Billing > Cost Explorer tomorrow: costs appear with a delay.\n'
