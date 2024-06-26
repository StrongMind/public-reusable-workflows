import pulumi 
import pulumi_aws as aws
import json
import os
import subprocess
from pulumi_aws import cloudwatch
import sys
from strongmind_deployment.secrets import SecretsComponent

class BatchComponent(pulumi.ComponentResource):
    def __init__(self, name, **kwargs):
        super().__init__("custom:module:BatchComponent", name, {})
        self.env_name = os.environ.get('ENVIRONMENT_NAME', 'stage')
        self.kwargs = kwargs
        self.max_vcpus = self.kwargs.get('max_vcpus', 16)
        self.vcpu = self.kwargs.get('vcpu', 0.25)
        self.max_memory = self.kwargs.get('max_memory', 2048)
        self.memory = self.kwargs.get('memory', 512)
        self.command = self.kwargs.get('command', ["echo", "hello world"])
        self.cron = self.kwargs.get('cron', 'cron(0 0 * * ? *)')
        self.secrets = self.kwargs.get('secrets', [])


        stack = pulumi.get_stack()
        region = "us-west-2"
        config = pulumi.Config()
        project = pulumi.get_project()
        self.project_stack = f"{project}-{stack}"

        git_root = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], cwd=".").decode('utf-8').strip()
        with open(f'{git_root}/CODEOWNERS', 'r') as file:
            owning_team = [line.strip().split('@')[-1] for line in file if '@' in line][-1].split('/')[1]

        tags = {
            "product": project,
            "repository": project,
            "service": project,
            "environment": self.env_name,
            "owner": owning_team,
        }

        default_vpc = aws.ec2.get_vpc(default="true")

        default_vpc = aws.ec2.get_vpc(default=True)
        security_group  = aws.ec2.get_security_group(name="default", vpc_id=default_vpc.id)
        default_sec_group = []
        default_sec_group.append(security_group.id) 
        default_subnets = aws.ec2.get_subnets(filters=[aws.ec2.GetSubnetsFilterArgs(
            name="vpc-id",
            values=[default_vpc.id]
        )])

        self.execution_role = aws.iam.Role(
            f"{self.project_stack}-execution-role",
            name=f"{self.project_stack}-execution-role",
            assume_role_policy=json.dumps(
                {
                    "Version": "2008-10-17",
                    "Statement": [
                        {
                            "Sid": "",
                            "Effect": "Allow",
                            "Principal": {
                                "Service": [
                                    "ecs-tasks.amazonaws.com",
                                    "batch.amazonaws.com",
                                    "events.amazonaws.com"
                            ]},
                            "Action": "sts:AssumeRole",
                        }
                    ],
                }
            ),
            tags=tags,
            opts=pulumi.ResourceOptions(parent=self),
        )
        self.execution_policy = aws.iam.RolePolicy(
            f"{self.project_stack}-execution-policy",
            name=f"{self.project_stack}-execution-policy",
            role=self.execution_role.id,
            policy=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Action": [
                                "ecs:*",
                                "ecr:GetAuthorizationToken",
                                "ecr:BatchCheckLayerAvailability",
                                "batch:*",
                                "events:*",
                                "s3:*",
                                "ecr:GetDownloadUrlForLayer",
                                "ecr:BatchGetImage",
                                "ecr:GetRepositoryPolicy",
                                "ecr:DescribeRepositories",
                                "ecr:ListImages",
                                "ecr:DescribeImages",
                                "ecr:InitiateLayerUpload",
                                "ecr:UploadLayerPart",
                                "ecr:CompleteLayerUpload",
                                "ecr:PutImage",
                                "logs:*",
                                "secretsmanager:GetSecretValue",
                                "ec2:*",
                                "iam:GetInstanceProfile",
				                "iam:GetRole",
				                "iam:PassRole",
                            ],
                            "Effect": "Allow",
                            "Resource": "*",
                        }
                    ],
                }
            ),
            opts=pulumi.ResourceOptions(parent=self),
        )

        self.create_env = aws.batch.ComputeEnvironment(f"{self.project_stack}-batch",
            compute_environment_name=f"{self.project_stack}-batch",
            compute_resources=aws.batch.ComputeEnvironmentComputeResourcesArgs( 
                max_vcpus=self.max_vcpus,
                security_group_ids=default_sec_group,
                subnets=default_subnets.ids,
                type="FARGATE",
                ),
            type="MANAGED",
            tags=tags,
            service_role=self.execution_role.arn,
            )

        self.queue = aws.batch.JobQueue(f"{self.project_stack}-queue",
            name=f"{self.project_stack}-queue",
            opts=pulumi.ResourceOptions(parent=self, depends_on=[self.create_env]),
            compute_environments=[self.create_env.arn],
            priority=1,
            state="ENABLED",
            tags=tags,
        )

        CONTAINER_IMAGE = os.environ['CONTAINER_IMAGE']

        self.logGroup = aws.cloudwatch.LogGroup(
            f"{self.project_stack}-log-group",
            name=f"/aws/batch/{self.project_stack}-job",
            retention_in_days=14,
            tags=tags
        )

        secrets = SecretsComponent("secrets", secret_string='{}')
        secretsList = secrets.get_secrets()

        containerProperties = pulumi.Output.all(
            command=self.command, 
            CONTAINER_IMAGE=CONTAINER_IMAGE, 
            memory=self.memory,
            vcpu=self.vcpu,
            execution_role=self.execution_role.arn,
            secretsList=secretsList,
            logGroup=self.logGroup.id,
            region=region
        ).apply(lambda args: json.dumps( {
            "command": args["command"],
            "image": args["CONTAINER_IMAGE"],
            "resourceRequirements": [
                {"type": "MEMORY", "value": str(args["memory"])},
                {"type": "VCPU", "value": str(args["vcpu"])}
            ],
            "executionRoleArn": args["execution_role"],
            "jobRoleArn": args["execution_role"],
            "networkConfiguration":
                {"assignPublicIp": "ENABLED"},
            "logConfiguration": {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": args["logGroup"],
                    "awslogs-region": args["region"],
                    "awslogs-stream-prefix": "batch"
                }
            },
            "secrets": args["secretsList"]
        }))

        self.definition = aws.batch.JobDefinition(
            f"{self.project_stack}-definition",
            name = f"{self.project_stack}-definition",
            type="container",
            platform_capabilities=["FARGATE"],
            container_properties=containerProperties,
            tags=tags
        )

        self.rule = aws.cloudwatch.EventRule(
            f"{self.project_stack}-eventbridge-rule",
            name=f"{self.project_stack}-eventbridge-rule",
            schedule_expression=self.cron,
            state="ENABLED",
            tags=tags
        )

        self.event_target = aws.cloudwatch.EventTarget(
            f"{self.project_stack}-event-target",
            rule=self.rule.name,
            arn=self.queue.arn,
            role_arn=self.execution_role.arn,
            batch_target=cloudwatch.EventTargetBatchTargetArgs(
                job_definition=self.definition.arn,
                job_name=self.definition.name,
                job_attempts=1
                ),
        )