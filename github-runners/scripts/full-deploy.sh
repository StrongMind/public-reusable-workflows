#!/bin/bash
set -e

# Complete deployment script - builds image and deploys infrastructure

# Configuration
AWS_ACCOUNT_ID=${AWS_ACCOUNT_ID:-058264302180}
AWS_REGION=${AWS_REGION:-us-west-2}
ENVIRONMENT_NAME=${ENVIRONMENT_NAME:-stage}
STACK_NAME=${STACK_NAME:-stage}

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Complete GitHub Runners Deployment${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Environment: $ENVIRONMENT_NAME"
echo "AWS Account: $AWS_ACCOUNT_ID"
echo "AWS Region: $AWS_REGION"
echo ""

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Step 1: Build and push Docker image
echo -e "${YELLOW}Step 1/3: Building and pushing Docker image...${NC}"
"$SCRIPT_DIR/build-and-push.sh"

echo ""
echo -e "${GREEN}✓ Docker image built and pushed${NC}"
echo ""

# Step 2: Deploy infrastructure
echo -e "${YELLOW}Step 2/3: Deploying infrastructure with Pulumi...${NC}"
"$SCRIPT_DIR/deploy.sh"

echo ""
echo -e "${GREEN}✓ Infrastructure deployed${NC}"
echo ""

# Step 3: Check status
echo -e "${YELLOW}Step 3/3: Checking deployment status...${NC}"
sleep 10  # Give ECS a moment to start tasks

"$SCRIPT_DIR/check-status.sh"

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Deployment Complete!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Next steps:"
echo "  1. Monitor logs: aws logs tail /aws/ecs/github-runners --follow"
echo "  2. Check GitHub: https://github.com/organizations/strongmind/settings/actions/runners"
echo "  3. Test with a workflow using runs-on: ecs"
echo ""

