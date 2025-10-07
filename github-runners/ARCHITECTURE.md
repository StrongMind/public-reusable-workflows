# GitHub Runners Architecture

## Overview

This infrastructure deploys 100 ephemeral, self-hosted GitHub runners to AWS ECS Fargate in the Strong-Mind-Stage account. The runners are pre-configured with Ruby 3.2.6 and connect to the `strongmind` GitHub organization.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      GitHub (strongmind org)                     │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Self-hosted Runners (labeled: ecs)                      │   │
│  │  - Register via ACCESS_TOKEN                             │   │
│  │  - Ephemeral (removed after each job)                    │   │
│  └─────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ HTTPS (Registration & Job Polling)
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                    AWS Strong-Mind-Stage                         │
│                      (Account: 058264302180)                     │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐│
│  │                    VPC (default)                            ││
│  │                                                              ││
│  │  ┌───────────────────────────────────────────────────────┐ ││
│  │  │  ECS Cluster: github-runners                          │ ││
│  │  │                                                         │ ││
│  │  │  ┌─────────────────────────────────────────────────┐  │ ││
│  │  │  │  ECS Service: github-runners                    │  │ ││
│  │  │  │  - Desired Count: 100                           │  │ ││
│  │  │  │  - Launch Type: FARGATE                         │  │ ││
│  │  │  │  - Public IP: Enabled (for GitHub access)       │  │ ││
│  │  │  │                                                   │  │ ││
│  │  │  │  ┌─────────────────────────────────────────┐    │  │ ││
│  │  │  │  │  Task Definition: github-runners        │    │  │ ││
│  │  │  │  │  - CPU: 2048 (2 vCPUs)                  │    │  │ ││
│  │  │  │  │  - Memory: 4096 MB (4 GB)               │    │  │ ││
│  │  │  │  │  - Image: ECR/github-runners:latest     │    │  │ ││
│  │  │  │  │                                           │    │  │ ││
│  │  │  │  │  Container:                              │    │  │ ││
│  │  │  │  │  - myoung34/github-runner:latest        │    │  │ ││
│  │  │  │  │  - Ruby 3.2.6 (pre-installed)           │    │  │ ││
│  │  │  │  │  - Env: ORG_NAME=strongmind              │    │  │ ││
│  │  │  │  │  - Env: LABELS=ecs                       │    │  │ ││
│  │  │  │  │  - Env: EPHEMERAL=true                   │    │  │ ││
│  │  │  │  │  - Secret: ACCESS_TOKEN (from SM)        │    │  │ ││
│  │  │  │  └─────────────────────────────────────────┘    │  │ ││
│  │  │  │                                                   │  │ ││
│  │  │  │  Tasks: [Task 1] [Task 2] ... [Task 100]        │  │ ││
│  │  │  └─────────────────────────────────────────────────┘  │ ││
│  │  └───────────────────────────────────────────────────────┘ ││
│  └────────────────────────────────────────────────────────────┘│
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐│
│  │  Supporting Resources                                       ││
│  │                                                              ││
│  │  ┌──────────────────┐  ┌──────────────────┐               ││
│  │  │  ECR Repository  │  │  Secrets Manager │               ││
│  │  │  github-runners  │  │  GitHub Token    │               ││
│  │  └──────────────────┘  └──────────────────┘               ││
│  │                                                              ││
│  │  ┌──────────────────┐  ┌──────────────────┐               ││
│  │  │  CloudWatch Logs │  │  IAM Roles       │               ││
│  │  │  /aws/ecs/...    │  │  Task/Exec Roles │               ││
│  │  └──────────────────┘  └──────────────────┘               ││
│  └────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Docker Image

**Base Image**: `myoung34/github-runner:latest`
- Industry-standard GitHub Actions runner container
- Handles runner registration, job execution, and cleanup
- Supports ephemeral mode

**Custom Additions**:
- Ruby 3.2.6 (via rbenv)
- Ruby build dependencies
- Configured for ARM64 architecture

**Location**: ECR `github-runners` repository

### 2. ECS Infrastructure

#### ECS Cluster
- **Name**: `github-runners`
- **Type**: Fargate (serverless)
- **Region**: us-west-2
- **Container Insights**: Enabled

#### ECS Service
- **Name**: `github-runners`
- **Desired Count**: 100 (configurable)
- **Launch Type**: Fargate
- **Network**: Public subnets with public IP
- **Deployment**: Rolling updates (200% max)

#### Task Definition
- **Family**: `github-runners`
- **CPU**: 2048 units (2 vCPUs)
- **Memory**: 4096 MB (4 GB)
- **Network Mode**: awsvpc
- **Requires Compatibilities**: FARGATE

### 3. IAM Roles

#### Task Execution Role
Permissions:
- Pull images from ECR
- Write logs to CloudWatch
- Read secrets from Secrets Manager

#### Task Role
Permissions:
- Execute commands in container (ECS Exec)
- Assume cross-account roles
- Access S3 (for workflow artifacts)
- Send SES emails

### 4. Secrets Management

**AWS Secrets Manager**:
- Secret Name: `github-runners-stage-token`
- Contains: GitHub Personal Access Token
- Rotation: Manual (consider implementing auto-rotation)

**Required Token Scopes**:
- `repo`: Full control of private repositories
- `admin:org`: Full control of orgs and teams
- `workflow`: Update GitHub Actions workflows

### 5. Logging and Monitoring

**CloudWatch Log Group**:
- Name: `/aws/ecs/github-runners`
- Retention: 14 days
- Stream per task

**Metrics**:
- `RunningTaskCount`: Number of running tasks
- `CPUUtilization`: CPU usage percentage
- `MemoryUtilization`: Memory usage percentage
- `DesiredTaskCount`: Target number of tasks

## Data Flow

### 1. Runner Registration
```
ECS Task Start
    ↓
Container starts with myoung34/github-runner
    ↓
Reads ACCESS_TOKEN from Secrets Manager
    ↓
Connects to GitHub API (api.github.com)
    ↓
Registers as self-hosted runner
    ↓
Labels: ["self-hosted", "ecs"]
    ↓
Polls for jobs (long-polling)
```

### 2. Job Execution
```
GitHub Workflow triggers (runs-on: ecs)
    ↓
GitHub assigns job to available runner
    ↓
Runner downloads repository
    ↓
Executes workflow steps
    ↓
Uploads logs/artifacts to GitHub
    ↓
Reports job status (success/failure)
    ↓
Runner de-registers (EPHEMERAL=true)
    ↓
ECS restarts task (new runner instance)
```

### 3. Logs and Monitoring
```
Container stdout/stderr
    ↓
CloudWatch Logs Agent
    ↓
/aws/ecs/github-runners
    ↓
Available for querying/streaming
```

## Infrastructure as Code

**Tool**: Pulumi (Python)

**Key Resources**:
```python
ContainerComponent(
    "github-runners",
    container_image=ecr_image,
    desired_count=100,
    cpu=2048,
    memory=4096,
    env_vars={...},
    secrets=[...],
    need_load_balancer=False  # No ALB needed
)
```

**Deployment**:
- State stored in Pulumi Cloud
- Stack: `stage` (or `prod`)
- Config: Encrypted

## Networking

### Egress (Outbound)
- GitHub API: `api.github.com:443`
- GitHub Actions: `*.actions.githubusercontent.com:443`
- Package registries (RubyGems, etc.): Various
- ECR: Via VPC endpoint or NAT gateway

### Ingress (Inbound)
- None required (runners poll for jobs)
- No load balancer
- No exposed ports

### Security Groups
- Egress: Allow all (runners need access to various services)
- Ingress: None

## Scaling

### Current Configuration
- **Fixed**: 100 tasks
- **No auto-scaling** (yet)

### Future Considerations

#### Option 1: Time-based Scaling
Scale up during business hours:
```python
scheduled_scaling=True,
pre_scale_time="08:00",
post_scale_time="18:00",
peak_min_capacity=100,
desired_web_count=20  # Off-peak
```

#### Option 2: Queue-based Scaling
Scale based on pending jobs:
- Monitor GitHub Actions queue via API
- Lambda function checks queue depth
- Updates ECS desired count

#### Option 3: Event-driven Scaling
- GitHub webhook for workflow_job events
- Trigger Lambda to scale up
- Scale down after cooldown period

## Cost Analysis

### Monthly Cost Estimate (100 runners, 24/7)

**Fargate Costs**:
- vCPU: 2 × $0.04048/hour × 100 × 730 hours = ~$5,910
- Memory: 4 GB × $0.004445/GB/hour × 100 × 730 hours = ~$1,298
- **Subtotal**: ~$7,208/month

**Data Transfer**:
- GitHub API: Minimal
- Docker pulls: ~$20/month (within free tier)
- CloudWatch Logs: ~$50/month

**Total**: ~$7,300/month

### Cost Optimization Options

1. **Time-based scaling**: Save 60% (~$4,380/month)
   - 100 runners during business hours (10 hrs/day)
   - 20 runners off-hours
   
2. **EC2 with Reserved Instances**: Save 40-60%
   - Requires operational overhead
   - Better for predictable workloads

3. **Spot instances**: Save 70%
   - Fargate Spot not available for ECS tasks yet
   - Consider EC2 Spot for runner hosts

## Security Considerations

### Secrets
- ✅ GitHub token stored in Secrets Manager (encrypted)
- ✅ Token auto-rotated (set up rotation lambda)
- ✅ Least privilege IAM roles

### Network
- ✅ Runners in public subnets (need outbound to GitHub)
- ✅ No inbound access
- ⚠️ Consider VPC endpoints for AWS services

### Container
- ✅ Ephemeral runners (fresh for each job)
- ⚠️ Running as root (required by base image)
- ✅ No Docker socket access (Fargate limitation)

### Compliance
- Audit logs in CloudWatch
- Runner activity tracked in GitHub
- Consider enabling GuardDuty for threat detection

## Limitations and Trade-offs

### Current Limitations

1. **No Docker-in-Docker**
   - Fargate doesn't support Docker socket mounting
   - Workflows needing Docker won't work
   - Workaround: Use Kaniko or BuildKit

2. **Fixed IP Pool**
   - Runners get new IP on each restart
   - Cannot whitelist by IP
   - Consider NAT Gateway with Elastic IPs

3. **Cold Start Time**
   - ~60-90 seconds for task to start
   - Runner registration: ~10-20 seconds
   - Total: ~2 minutes before job execution

### Design Trade-offs

| Decision | Pro | Con |
|----------|-----|-----|
| Fargate | Serverless, no maintenance | Can't mount Docker socket |
| 100 tasks | High throughput | $7K+/month |
| Ephemeral | Secure, fresh state | Higher overhead |
| Public IPs | Simple GitHub access | Cost, IP exhaustion |
| Fixed count | Predictable | Not cost-optimized |

## Disaster Recovery

### Failure Scenarios

1. **Single task failure**
   - ECS automatically restarts
   - Service maintains desired count
   - No impact on other runners

2. **Service failure**
   - Unlikely with Fargate
   - Pulumi can recreate from code
   - Recovery time: ~5 minutes

3. **Region failure**
   - Deploy multi-region setup
   - Or: Fallback to GitHub-hosted runners
   - RTO: Manual failover, ~30 minutes

4. **GitHub API outage**
   - Runners retry connection
   - Tasks continue running
   - Jobs queue until recovery

### Backup and Recovery

**State**:
- Pulumi state: Backed up in Pulumi Cloud
- No persistent data on runners (ephemeral)

**Secrets**:
- GitHub token: Manual backup recommended
- Secrets Manager: Enable automatic backup

**Recovery Steps**:
1. Ensure GitHub token is valid
2. Run `pulumi up` to recreate infrastructure
3. Verify runners appear in GitHub
4. Test with sample workflow

## Future Enhancements

### Short-term (1-3 months)
- [ ] Implement queue-based auto-scaling
- [ ] Set up CloudWatch dashboards
- [ ] Configure alerts for failures
- [ ] Add cost anomaly detection

### Medium-term (3-6 months)
- [ ] Multi-region deployment for HA
- [ ] Implement token auto-rotation
- [ ] Add custom AMI with Docker pre-configured
- [ ] Explore EC2 option for Docker support

### Long-term (6+ months)
- [ ] Kubernetes-based runners (EKS)
- [ ] Advanced autoscaling (ML-based predictions)
- [ ] Self-service runner provisioning
- [ ] Runner pool per team/project

## References

- [GitHub Actions Self-hosted Runners](https://docs.github.com/en/actions/hosting-your-own-runners)
- [myoung34/github-runner Docker Image](https://github.com/myoung34/docker-github-actions-runner)
- [AWS ECS Fargate](https://aws.amazon.com/fargate/)
- [Pulumi AWS Provider](https://www.pulumi.com/registry/packages/aws/)

