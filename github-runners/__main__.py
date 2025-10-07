"""
GitHub Runners ECS Infrastructure
Deploys 100 self-hosted GitHub runners to ECS for the strongmind organization
"""
import os
import sys
import pulumi
import pulumi_aws as aws

# Add parent directory to path to import strongmind_deployment
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'deployment', 'src'))
from strongmind_deployment.container import ContainerComponent

# Get the current stack
stack = pulumi.get_stack()
project = pulumi.get_project()

# Get configuration
config = pulumi.Config("github-runners")

# Get the VPC - use existing VPC in the account
# VPC ID can be configured per stack, or use the default for stage
vpc_id = config.get("vpc_id") or "vpc-0d01fd72b5fb9d965"  # Default to stage VPC

# Get all subnets in this VPC
subnets = aws.ec2.get_subnets(
    filters=[
        aws.ec2.GetSubnetsFilterArgs(
            name="vpc-id",
            values=[vpc_id]
        )
    ]
)

# Get additional configuration
github_token = config.require_secret("github_token")
runner_count = config.get_int("runner_count") or 100
cpu = config.get_int("cpu") or 2048
memory = config.get_int("memory") or 4096

# Set environment variables
env_name = os.environ.get('ENVIRONMENT_NAME', 'stage')
account_id = os.environ.get('AWS_ACCOUNT_ID', '058264302180')  # Strong-Mind-Stage account

# Container image - will be built and pushed to ECR
ecr_registry = f"{account_id}.dkr.ecr.us-west-2.amazonaws.com"
image_name = f"{ecr_registry}/{project}:latest"

# Try to use existing ECR repository, create if it doesn't exist
try:
    existing_ecr = aws.ecr.get_repository(name="github-runners")
    ecr_repo_name = existing_ecr.name
    ecr_repo_url = existing_ecr.repository_url
    ecr_repo_arn = existing_ecr.arn
    pulumi.log.info(f"Using existing ECR repository: {ecr_repo_url}")
    # Create a dummy resource to maintain exports
    class ExistingECRRepo:
        def __init__(self, name, url, arn):
            self.name = name
            self.repository_url = url
            self.arn = arn
    ecr_repo = ExistingECRRepo(ecr_repo_name, ecr_repo_url, ecr_repo_arn)
except:
    # Create ECR repository for the GitHub runner image
    ecr_repo = aws.ecr.Repository(
        "github-runners-repo",
        name="github-runners",
        image_scanning_configuration=aws.ecr.RepositoryImageScanningConfigurationArgs(
            scan_on_push=True,
        ),
        image_tag_mutability="MUTABLE",
        tags={
            "product": project,
            "repository": project,
            "service": "github-runners",
            "environment": env_name,
            "owner": "platform",
        }
    )
    ecr_repo_name = ecr_repo.name
    ecr_repo_url = ecr_repo.repository_url
    ecr_repo_arn = ecr_repo.arn

# Create lifecycle policy to keep only the last 10 images (only if we created the repo)
try:
    if isinstance(ecr_repo, aws.ecr.Repository):
        lifecycle_policy = aws.ecr.LifecyclePolicy(
            "github-runners-lifecycle",
            repository=ecr_repo.name,
            policy="""{
                "rules": [
                    {
                        "rulePriority": 1,
                        "description": "Keep last 10 images",
                        "selection": {
                            "tagStatus": "any",
                            "countType": "imageCountMoreThan",
                            "countNumber": 10
                        },
                        "action": {
                            "type": "expire"
                        }
                    }
                ]
            }"""
        )
except:
    pass  # Skip lifecycle policy if using existing repo

# Environment variables for the GitHub runners
env_vars = {
    "RUNNER_SCOPE": "org",
    "ORG_NAME": "strongmind",
    "LABELS": "ecs",
    "EPHEMERAL": "true",
    "DISABLE_AUTOMATIC_DEREGISTRATION": "false",
    "RUN_AS_ROOT": "true",
    "RUNNER_WORKDIR": "/tmp/runner/work",
}

# Create secrets for sensitive data
# The GitHub token needs to be stored in AWS Secrets Manager
secrets_manager_secret = aws.secretsmanager.Secret(
    "github-runner-token",
    name=f"github-runners-{env_name}-token",
    description="GitHub Personal Access Token for self-hosted runners",
    tags={
        "product": project,
        "repository": project,
        "service": "github-runners",
        "environment": env_name,
        "owner": "platform",
    }
)

# Store the token value
secret_version = aws.secretsmanager.SecretVersion(
    "github-runner-token-version",
    secret_id=secrets_manager_secret.id,
    secret_string=github_token,
)

# Secrets to pass to the container
secrets = [
    {
        "name": "ACCESS_TOKEN",
        "value_from": secrets_manager_secret.arn,
    }
]

# Deploy the GitHub runners using ContainerComponent
# Note: This uses Fargate by default. For Docker-in-Docker support,
# you may need to switch to EC2-backed ECS instances
github_runners = ContainerComponent(
    "github-runners",
    namespace="github-runners",
    need_load_balancer=False,  # Runners don't need a load balancer
    container_image=image_name,
    container_port=8080,  # Not really used, but required
    cpu=cpu,
    memory=memory,
    env_vars=env_vars,
    secrets=secrets,
    desired_count=runner_count,
    deployment_maximum_percent=200,  # Allow rolling deployments
    vpc_id=vpc_id,  # Pass the VPC ID
    subnet_ids=subnets.ids,  # Pass the subnet IDs
    needs_s3_access=False,  # GitHub runners don't need S3 access
    # Note: Fargate doesn't support Docker socket mounting
    # For full Docker support, consider EC2-backed ECS with appropriate user data
)

# Export important values
pulumi.export("ecr_repository_url", ecr_repo_url if 'ecr_repo_url' in locals() else ecr_repo.repository_url)
pulumi.export("ecr_repository_name", ecr_repo_name if 'ecr_repo_name' in locals() else ecr_repo.name)
pulumi.export("ecs_cluster_name", github_runners.ecs_cluster.name)
pulumi.export("ecs_service_name", github_runners.fargate_service.service.name)
pulumi.export("runner_count", runner_count)
pulumi.export("secrets_manager_secret_name", secrets_manager_secret.name)
pulumi.export("secrets_manager_secret_arn", secrets_manager_secret.arn)

