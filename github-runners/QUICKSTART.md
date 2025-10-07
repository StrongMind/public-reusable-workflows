# GitHub Runners - Quick Start Guide

This is a **TL;DR** version for deploying 100 GitHub self-hosted runners to ECS. For detailed information, see [README.md](README.md).

## Prerequisites Checklist

- [ ] AWS CLI installed and configured
- [ ] Docker installed and running
- [ ] Python 3.11+ installed
- [ ] Pulumi CLI installed ([install](https://www.pulumi.com/docs/install/))
- [ ] AWS credentials for Strong-Mind-Stage account (058264302180)
- [ ] GitHub Personal Access Token with `repo` and `admin:org` scopes

## Deploy in 5 Minutes

### 1. Set Environment Variables
```bash
export AWS_ACCOUNT_ID=058264302180
export AWS_REGION=us-west-2
export ENVIRONMENT_NAME=stage
```

### 2. Login to Pulumi Backend
```bash
pulumi login s3://pulumi-backend-${AWS_ACCOUNT_ID}/github-runners
```

### 3. Run Full Deployment
```bash
cd github-runners
./scripts/full-deploy.sh
```

When prompted, enter your GitHub Personal Access Token.

**That's it!** The script will automatically handle the Pulumi login and:
1. Build and push the Docker image to ECR
2. Deploy the ECS infrastructure with Pulumi
3. Check the deployment status

## Verify Deployment

```bash
# Check ECS service
./scripts/check-status.sh

# Watch logs
aws logs tail /aws/ecs/github-runners --follow

# Check GitHub
open https://github.com/organizations/strongmind/settings/actions/runners
```

## Use in Workflows

```yaml
jobs:
  test:
    runs-on: ecs  # Use the 'ecs' label
    steps:
      - uses: actions/checkout@v4
      - name: Run tests
        run: bundle exec rspec
```

## Common Tasks

### Update Runner Count
```bash
./scripts/update-runner-count.sh 150
```

### Update Docker Image
```bash
./scripts/build-and-push.sh
cd github-runners && pulumi up
```

### View Status
```bash
./scripts/check-status.sh
```

### Destroy Everything
```bash
cd github-runners
pulumi destroy
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Runners not appearing | Check GitHub token in Secrets Manager |
| Tasks won't start | Verify ECR image exists |
| High costs | Consider time-based scaling (see SETUP.md) |
| Need Docker support | See README.md for EC2-backed option |

## Cost

- **~$7,300/month** for 100 runners (24/7)
- **~$2,900/month** with 60% time-based scaling

## Important Notes

⚠️ **Fargate Limitation**: Cannot run Docker-in-Docker. Use Kaniko or BuildKit for image builds, or switch to EC2-backed ECS.

✅ **Ephemeral Runners**: Runners are destroyed after each job for security.

✅ **Ruby 3.2.6**: Pre-installed and ready to use.

## Documentation

- **Quick Start**: You're reading it!
- **Setup Guide**: [SETUP.md](SETUP.md) - Detailed deployment instructions
- **Architecture**: [ARCHITECTURE.md](ARCHITECTURE.md) - System design and components
- **README**: [README.md](README.md) - Complete reference

## Support

Questions? Contact @strongmind/platform-team

