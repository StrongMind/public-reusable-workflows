#!/bin/bash
set -e

# Script to check the status of the GitHub runners deployment

# Disable AWS CLI pager
export AWS_PAGER=""

AWS_ACCOUNT_ID=${AWS_ACCOUNT_ID:-058264302180}
AWS_REGION=${AWS_REGION:-us-west-2}
CLUSTER_NAME="github-runners-github-runners"
SERVICE_NAME="github-runners-github-runners"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  GitHub Runners Status Check${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Check ECS Service Status
echo -e "${YELLOW}ECS Service Status:${NC}"
aws ecs describe-services \
  --cluster $CLUSTER_NAME \
  --services $SERVICE_NAME \
  --query 'services[0].[serviceName,status,runningCount,desiredCount,pendingCount]' \
  --output table

echo ""
echo -e "${YELLOW}Recent Task Status:${NC}"
TASK_ARNS=$(aws ecs list-tasks --cluster $CLUSTER_NAME --service-name $SERVICE_NAME --query 'taskArns[0:5]' --output text)

if [ -n "$TASK_ARNS" ]; then
  aws ecs describe-tasks \
    --cluster $CLUSTER_NAME \
    --tasks $TASK_ARNS \
    --query 'tasks[].[taskArn,lastStatus,healthStatus,connectivity]' \
    --output table
else
  echo "No tasks found"
fi

echo ""
echo -e "${YELLOW}Recent Events:${NC}"
aws ecs describe-services \
  --cluster $CLUSTER_NAME \
  --services $SERVICE_NAME \
  --query 'services[0].events[0:5].[createdAt,message]' \
  --output table

echo ""
echo -e "${YELLOW}CloudWatch Logs (last 10 lines):${NC}"
aws logs tail /aws/ecs/github-runners --since 5m --format short 2>/dev/null | tail -n 10 || echo "No recent logs"

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "To view live logs:"
echo "  aws logs tail /aws/ecs/github-runners --follow"
echo ""
echo "To check GitHub runners:"
echo "  https://github.com/organizations/strongmind/settings/actions/runners"
echo ""

