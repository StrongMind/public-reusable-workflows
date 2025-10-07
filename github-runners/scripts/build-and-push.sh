#!/bin/bash
set -e

# Script to build and push the GitHub runner Docker image to ECR

# Disable AWS CLI pager
export AWS_PAGER=""

# Configuration
AWS_ACCOUNT_ID=${AWS_ACCOUNT_ID:-058264302180}
AWS_REGION=${AWS_REGION:-us-west-2}
IMAGE_NAME="github-runners"
IMAGE_TAG=${IMAGE_TAG:-latest}

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Building and pushing GitHub runner image to ECR${NC}"
echo "Account: $AWS_ACCOUNT_ID"
echo "Region: $AWS_REGION"
echo "Image: $IMAGE_NAME:$IMAGE_TAG"
echo ""

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "Error: AWS CLI is not installed"
    exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed"
    exit 1
fi

# Login to ECR
echo -e "${YELLOW}Logging in to ECR...${NC}"
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

# Create ECR repository if it doesn't exist
echo -e "${YELLOW}Ensuring ECR repository exists...${NC}"
aws ecr describe-repositories --repository-names $IMAGE_NAME --region $AWS_REGION 2>/dev/null || \
    aws ecr create-repository --repository-name $IMAGE_NAME --region $AWS_REGION \
        --image-scanning-configuration scanOnPush=true \
        --tags Key=service,Value=github-runners Key=environment,Value=stage

# Build the image
echo -e "${YELLOW}Building Docker image...${NC}"
cd "$(dirname "$0")/../.."  # Go to repo root
docker build -t $IMAGE_NAME:$IMAGE_TAG -f Dockerfile .

# Tag for ECR
ECR_IMAGE="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${IMAGE_NAME}:${IMAGE_TAG}"
echo -e "${YELLOW}Tagging image for ECR: $ECR_IMAGE${NC}"
docker tag $IMAGE_NAME:$IMAGE_TAG $ECR_IMAGE

# Push to ECR
echo -e "${YELLOW}Pushing image to ECR...${NC}"
docker push $ECR_IMAGE

echo -e "${GREEN}✓ Successfully pushed image to ECR${NC}"
echo "Image URI: $ECR_IMAGE"

