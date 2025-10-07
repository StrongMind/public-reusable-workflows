#!/bin/bash
set -e

# Script to deploy the GitHub runners infrastructure using Pulumi

# Configuration
AWS_ACCOUNT_ID=${AWS_ACCOUNT_ID:-058264302180}
AWS_REGION=${AWS_REGION:-us-west-2}
ENVIRONMENT_NAME=${ENVIRONMENT_NAME:-stage}
STACK_NAME=${STACK_NAME:-stage}

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Deploying GitHub runners infrastructure${NC}"
echo "Environment: $ENVIRONMENT_NAME"
echo "Stack: $STACK_NAME"
echo "AWS Account: $AWS_ACCOUNT_ID"
echo "AWS Region: $AWS_REGION"
echo ""

# Check if Pulumi is installed
if ! command -v pulumi &> /dev/null; then
    echo "Error: Pulumi is not installed"
    echo "Install it from: https://www.pulumi.com/docs/install/"
    exit 1
fi

# Navigate to the github-runners directory
cd "$(dirname "$0")/.."

# Check if requirements are installed
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
fi

echo -e "${YELLOW}Installing/updating dependencies...${NC}"
source venv/bin/activate
pip install -q -r requirements.txt

# Login to Pulumi S3 backend
echo -e "${YELLOW}Logging in to Pulumi backend...${NC}"
pulumi login s3://pulumi-backend-${AWS_ACCOUNT_ID}/github-runners

# Check if stack exists
if ! pulumi stack select $STACK_NAME 2>/dev/null; then
    echo -e "${YELLOW}Creating new stack: $STACK_NAME${NC}"
    pulumi stack init $STACK_NAME
fi

# Check if GitHub token is configured
if ! pulumi config get github-runners:github_token &>/dev/null; then
    echo -e "${YELLOW}GitHub token not configured${NC}"
    echo "Please enter your GitHub Personal Access Token (with repo and admin:org scopes):"
    read -s GITHUB_TOKEN
    pulumi config set --secret github-runners:github_token "$GITHUB_TOKEN"
fi

# Set environment variables for Pulumi
export ENVIRONMENT_NAME=$ENVIRONMENT_NAME
export AWS_ACCOUNT_ID=$AWS_ACCOUNT_ID

# Deploy
echo -e "${YELLOW}Running Pulumi up...${NC}"
pulumi up

echo -e "${GREEN}✓ Deployment complete${NC}"
echo ""
echo "To view the deployed resources:"
echo "  pulumi stack output"
echo ""
echo "To view logs:"
echo "  aws logs tail /aws/ecs/github-runners --follow"

