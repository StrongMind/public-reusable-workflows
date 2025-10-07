# GitHub Runners ECS Infrastructure

This Pulumi project deploys 100 self-hosted GitHub runners to AWS ECS in the Strong-Mind-Stage account.

## Overview

The GitHub runners are configured to:
- Connect to the `strongmind` GitHub organization
- Run as ephemeral runners (auto-removed after each job)
- Be labeled with `ecs` for targeting specific workflows
- Run with Ruby 3.2.6 pre-installed (via the custom Dockerfile)

## Prerequisites

1. **AWS Credentials**: Ensure you have access to the Strong-Mind-Stage AWS account (058264302180)
2. **GitHub Token**: Create a GitHub Personal Access Token with `repo` and `admin:org` scopes
3. **Docker Image**: Build and push the Docker image to ECR before deploying

## Setup

### 1. Install Dependencies

```bash
cd github-runners
pip install -r requirements.txt
```

### 2. Login to Pulumi Backend

```bash
export AWS_ACCOUNT_ID=058264302180
pulumi login s3://pulumi-backend-${AWS_ACCOUNT_ID}/github-runners
```

### 3. Initialize Pulumi Stack

```bash
pulumi stack init stage
```

### 4. Configure the Stack

```bash
# Set the GitHub token (this will be encrypted)
pulumi config set --secret github-runners:github_token <your-github-token>

# Optional: Adjust runner count (default is 10)
pulumi config set github-runners:runner_count 100

# Optional: Adjust CPU and memory per runner
pulumi config set github-runners:cpu 2048
pulumi config set github-runners:memory 4096
```

**Note**: All configuration uses the `github-runners:` namespace. See [docs/PULUMI_BACKEND.md](docs/PULUMI_BACKEND.md) for Pulumi backend setup.

### 5. Build and Push Docker Image

Before deploying, you need to build and push the Docker image to ECR:

```bash
# Set your AWS account ID
export AWS_ACCOUNT_ID=058264302180
export AWS_REGION=us-west-2
export ENVIRONMENT_NAME=stage

# Login to ECR
aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.us-west-2.amazonaws.com

# Build the image (from the root directory)
cd ..
docker build -t github-runners:latest .

# Tag for ECR
docker tag github-runners:latest ${AWS_ACCOUNT_ID}.dkr.ecr.us-west-2.amazonaws.com/github-runners:latest

# Push to ECR
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.us-west-2.amazonaws.com/github-runners:latest
```

### 6. Deploy the Infrastructure

```bash
cd github-runners
export ENVIRONMENT_NAME=stage
export AWS_ACCOUNT_ID=058264302180
pulumi up
```

## Configuration

### Environment Variables

The runners are configured with the following environment variables:

- `RUNNER_SCOPE`: `org` (connect to organization, not repository)
- `ORG_NAME`: `strongmind`
- `LABELS`: `ecs` (label for targeting in workflows)
- `EPHEMERAL`: `true` (runners are removed after each job)
- `DISABLE_AUTOMATIC_DEREGISTRATION`: `false`
- `RUN_AS_ROOT`: `true`
- `RUNNER_WORKDIR`: `/tmp/runner/work`
- `ACCESS_TOKEN`: Stored securely in AWS Secrets Manager

### Resource Configuration

- **Default CPU**: 2048 units (2 vCPUs)
- **Default Memory**: 4096 MiB (4 GB)
- **Default Runner Count**: 100 tasks

You can adjust these values using `pulumi config set`.

## Important Considerations

### Docker Socket Access

⚠️ **Important**: The original docker-compose.yml mounts `/var/run/docker.sock`, which is **not supported in AWS Fargate**. 

If your workflows require Docker-in-Docker capabilities, you have two options:

#### Option 1: Switch to EC2-backed ECS (Recommended for Docker support)

Modify the infrastructure to use EC2 instances instead of Fargate. This requires:
1. Creating an ECS cluster with EC2 capacity
2. Setting up EC2 instances with Docker installed
3. Mounting the Docker socket from the host

#### Option 2: Use Docker-in-Docker (DinD)

Modify the Dockerfile to run Docker daemon inside the container (requires privileged mode).

For now, this infrastructure uses Fargate for simplicity. If Docker-in-Docker is required, we'll need to switch to EC2-backed ECS.

## Monitoring

The infrastructure creates:
- CloudWatch Log Group: `/aws/ecs/github-runners`
- ECS Cluster: `github-runners`
- ECS Service: `github-runners`

View logs:
```bash
aws logs tail /aws/ecs/github-runners --follow
```

## Updating

To update the runner count:

```bash
pulumi config set runner_count 150
pulumi up
```

To update the Docker image:

```bash
# Rebuild and push the image
docker build -t github-runners:latest ..
docker tag github-runners:latest ${AWS_ACCOUNT_ID}.dkr.ecr.us-west-2.amazonaws.com/github-runners:latest
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.us-west-2.amazonaws.com/github-runners:latest

# Update the ECS service to use the new image
pulumi up
```

## Cleanup

To destroy all resources:

```bash
pulumi destroy
```

## Troubleshooting

### Runners not appearing in GitHub

1. Check that the GitHub token has the correct permissions
2. Verify the token in Secrets Manager
3. Check ECS task logs for connection errors

### Tasks failing to start

1. Check that the Docker image exists in ECR
2. Verify the task role has permissions to pull from ECR
3. Check CloudWatch logs for errors

### Out of capacity

If you need more than 100 runners, adjust the `max_capacity` in the ContainerComponent or request a service quota increase from AWS.

## Using the Runners in Workflows

To use these runners in your GitHub Actions workflows:

```yaml
jobs:
  my-job:
    runs-on: ecs  # Use the 'ecs' label
    steps:
      - uses: actions/checkout@v3
      - name: Run tests
        run: bundle exec rspec
```

