#!/bin/bash
set -e

# Script to update the number of GitHub runners

if [ -z "$1" ]; then
    echo "Usage: $0 <new_runner_count>"
    echo "Example: $0 150"
    exit 1
fi

NEW_COUNT=$1
STACK_NAME=${STACK_NAME:-stage}

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Updating runner count to $NEW_COUNT${NC}"

# Navigate to the github-runners directory
cd "$(dirname "$0")/.."

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Select the stack
pulumi stack select $STACK_NAME

# Update the configuration
echo -e "${YELLOW}Setting runner_count to $NEW_COUNT...${NC}"
pulumi config set github-runners:runner_count $NEW_COUNT

# Deploy the change
echo -e "${YELLOW}Deploying changes...${NC}"
pulumi up

echo -e "${GREEN}✓ Runner count updated to $NEW_COUNT${NC}"

