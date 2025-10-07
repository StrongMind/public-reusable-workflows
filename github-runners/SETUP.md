# GitHub Runners ECS Setup Guide

This guide will walk you through deploying 100 self-hosted GitHub runners to AWS ECS.

## Quick Start

### Prerequisites

1. **AWS Access**: Credentials for Strong-Mind-Stage account (058264302180)
2. **GitHub Token**: Personal Access Token with `repo` and `admin:org` scopes
3. **Tools**: 
   - AWS CLI installed and configured
   - Docker installed
   - Python 3.11+ installed
   - Pulumi CLI installed

### One-Time Setup

1. **Clone the repository** (if not already done):
   ```bash
   cd /Users/pshippy9249/Dev/public-reusable-workflows
   ```

2. **Create your GitHub token**:
   - Go to https://github.com/settings/tokens
   - Click "Generate new token (classic)"
   - Select scopes: `repo`, `admin:org`, `workflow`
   - Copy the token (you'll need it shortly)

3. **Set environment variables**:
   ```bash
   export AWS_ACCOUNT_ID=058264302180
   export AWS_REGION=us-west-2
   export ENVIRONMENT_NAME=stage
   ```

4. **Build and push the Docker image**:
   ```bash
   cd github-runners
   ./scripts/build-and-push.sh
   ```
   
   This will:
   - Login to ECR
   - Create the ECR repository if needed
   - Build the Docker image
   - Push it to ECR

5. **Deploy the infrastructure**:
   ```bash
   ./scripts/deploy.sh
   ```
   
   When prompted, paste your GitHub token.
   
   This will:
   - Install Python dependencies
   - Initialize the Pulumi stack
   - Configure the GitHub token (encrypted)
   - Deploy 100 runner tasks to ECS

### Verify Deployment

1. **Check the ECS service**:
   ```bash
   aws ecs describe-services \
     --cluster github-runners \
     --services github-runners \
     --query 'services[0].[serviceName,status,runningCount,desiredCount]' \
     --output table
   ```

2. **View logs**:
   ```bash
   aws logs tail /aws/ecs/github-runners --follow
   ```

3. **Check GitHub**:
   - Go to https://github.com/organizations/strongmind/settings/actions/runners
   - You should see runners labeled with `ecs` appearing

## Configuration Options

### Change Runner Count

To deploy a different number of runners:

```bash
./scripts/update-runner-count.sh 150
```

### Change CPU/Memory

```bash
cd github-runners
pulumi config set cpu 4096      # 4 vCPUs
pulumi config set memory 8192   # 8 GB RAM
pulumi up
```

### Update Docker Image

After making changes to the Dockerfile:

```bash
./scripts/build-and-push.sh
cd github-runners
pulumi up  # Will detect the new image and update tasks
```

## Using the Runners in Workflows

Add this to your GitHub Actions workflow:

```yaml
name: My Workflow
on: [push]

jobs:
  test:
    runs-on: ecs  # Use the 'ecs' label
    steps:
      - uses: actions/checkout@v4
      - name: Setup Ruby
        uses: ruby/setup-ruby@v1
        with:
          ruby-version: 3.2.6
      - name: Run tests
        run: |
          bundle install
          bundle exec rspec
```

## Important Notes

### Docker-in-Docker Limitation

⚠️ **The current Fargate-based setup does not support Docker-in-Docker (DinD).**

If your workflows need to run Docker commands, you have two options:

#### Option A: Use Kaniko or similar tools (Recommended for Fargate)
- Use [Kaniko](https://github.com/GoogleContainerTools/kaniko) for building images without Docker daemon
- Use [BuildKit](https://github.com/moby/buildkit) in rootless mode

#### Option B: Switch to EC2-backed ECS
This requires modifying the infrastructure:
1. Create an EC2 Auto Scaling Group
2. Update the ECS cluster to use EC2 capacity
3. Modify the task definition to mount the Docker socket

Contact the platform team if you need EC2-backed runners.

### Security Considerations

- The GitHub token is stored encrypted in AWS Secrets Manager
- Runners are ephemeral (destroyed after each job)
- Runners run with root access (required by the base image)
- Network traffic goes through the VPC's NAT gateway

### Cost Estimates

With 100 runners running 24/7:
- **Fargate vCPU**: ~$0.04048/hour × 2 vCPUs × 100 = ~$292/day
- **Fargate Memory**: ~$0.004445/GB-hour × 4 GB × 100 = ~$43/day
- **Total**: ~$335/day or ~$10,000/month

Consider:
- Scaling down during off-hours
- Using EC2 with Reserved Instances for cost savings
- Implementing auto-scaling based on queue depth

## Troubleshooting

### Runners not connecting to GitHub

1. **Check the token**:
   ```bash
   aws secretsmanager get-secret-value \
     --secret-id github-runners-stage-token \
     --query SecretString \
     --output text
   ```

2. **Check task logs**:
   ```bash
   aws logs tail /aws/ecs/github-runners --follow --filter-pattern "ERROR"
   ```

3. **Verify token permissions**:
   - Token must have `repo`, `admin:org`, and `workflow` scopes
   - Token must not be expired
   - Organization must allow self-hosted runners

### Tasks failing to start

1. **Check ECR image exists**:
   ```bash
   aws ecr describe-images --repository-name github-runners
   ```

2. **Check task definition**:
   ```bash
   aws ecs describe-task-definition --task-definition github-runners
   ```

3. **Check IAM permissions**:
   - Task execution role must have `AmazonECSTaskExecutionRolePolicy`
   - Task role must have permissions for Secrets Manager

### Out of resources

If you get "RESOURCE:MEMORY" or "RESOURCE:CPU" errors:
- AWS has limits on Fargate resources per region
- Request a service quota increase in AWS Console
- Or reduce the runner count

## Monitoring

### CloudWatch Dashboards

View the ECS cluster dashboard:
```bash
aws cloudwatch get-dashboard --dashboard-name github-runners
```

### Metrics to Monitor

- `RunningTaskCount`: Should equal desired count
- `CPUUtilization`: Should be < 80%
- `MemoryUtilization`: Should be < 80%
- `TaskRegistrationErrors`: Should be 0

### Alerts

Set up CloudWatch alarms for:
- Service unhealthy
- High CPU/memory usage
- Failed task launches
- GitHub connection failures

## Cleanup

To remove all infrastructure:

```bash
cd github-runners
pulumi destroy
```

This will delete:
- ECS service and tasks
- ECS cluster
- CloudWatch log groups
- Secrets Manager secrets
- ECR repository (you may need to empty it first)

## Support

For issues or questions:
- Platform Team: @strongmind/platform-team
- Documentation: See README.md in this directory
- AWS Support: Use the AWS Console support center

