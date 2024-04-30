import pulumi 
import pulumi_aws as aws
import pulumi_awsx as awsx
import json
import os
import subprocess
from pulumi_aws import cloudwatch

class BatchComponent(pulumi.ComponentResource):
    def __init__(self, name, **kwargs):
        super().__init__("custom:module:BatchComponent", name, {})
        self.env_name = os.environ.get('ENVIRONMENT_NAME', 'stage')
        self.kwargs = kwargs
        self.max_vcpus = self.kwargs.get('max_vcpus', 0.25)
        self.max_memory = self.kwargs.get('max_memory', 2048)
        self.command = self.kwargs.get('command', '["echo", "hello world"]')
        self.cron = self.kwargs.get('cron', 'cron(0 0 * * ? *)')
        #self.image_id = image_id
        #self.json = json


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
        #default_vpc_id = default_vpc.vpc_id
        default_vpc_id = default_vpc.id

        default_vpc = aws.ec2.get_vpc(default=True)
        security_group  = aws.ec2.get_security_group(name="default", vpc_id=default_vpc.id)
        print(f"sec group is: {security_group.id}")
        #for dirattr in dir(default_security_group_resource):
            #print(f" attr is {dirattr} and the type is {type(dirattr)}")
        #exit()
        default_sec_group = []
        default_sec_group.append(security_group.id) 
        default_subnets = aws.ec2.get_subnets(filters=[aws.ec2.GetSubnetsFilterArgs(
            name="vpc-id",
            values=[default_vpc.id]
        )])
        default_subnet = []
        #default_subnet.append(default_vpc.public_subnet_ids) 
        print(f"subnet is: {default_subnets.ids}")
        execution_role = aws.iam.Role(
            f"{self.project_stack}-execution-role",
            name=f"{self.project_stack}-execution-role",
            assume_role_policy=json.dumps(
                {
                    "Version": "2008-10-17",
                    "Statement": [
                        {
                            "Sid": "",
                            "Effect": "Allow",
                            "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                            "Action": "sts:AssumeRole",
                        }
                    ],
                }
            ),
            tags=tags,
            opts=pulumi.ResourceOptions(parent=self),
        )
        execution_policy = aws.iam.RolePolicy(
            f"{self.project_stack}-execution-policy",
            name=f"{self.project_stack}-execution-policy",
            role=execution_role.id,
            policy=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Action": [
                                "ecs:*",
                                "ecr:GetAuthorizationToken",
                                "ecr:BatchCheckLayerAvailability",
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
                                "logs:CreateLogStream",
                                "logs:PutLogEvents",
                                "secretsmanager:GetSecretValue",
                            ],
                            "Effect": "Allow",
                            "Resource": "*",
                        }
                    ],
                }
            ),
            opts=pulumi.ResourceOptions(parent=self),
        )

        create_env = aws.batch.ComputeEnvironment(f"{self.project_stack}-batch",
            compute_environment_name=f"{self.project_stack}-batch",
            compute_resources=aws.batch.ComputeEnvironmentComputeResourcesArgs( max_vcpus=self.max_vcpus,
                security_group_ids=default_sec_group,
                subnets=default_subnets.ids,
                type="FARGATE",
                ),
            type="MANAGED",
            tags=tags,
            service_role="arn:aws:iam::221871915463:role/aws-service-role/batch.amazonaws.com/AWSServiceRoleForBatch",
            ) 


        sch_policy = aws.batch.SchedulingPolicy(f"{self.project_stack}-sch_policy",
            name=f"{self.project_stack}-sch_policy",
            fair_share_policy=aws.batch.SchedulingPolicyFairSharePolicyArgs(
                share_distributions=[
                    aws.batch.SchedulingPolicyFairSharePolicyShareDistributionArgs(
                        share_identifier="A1*",
                        weight_factor=1
                        )
                    ]
                ),
                tags=tags
            )

        queue = aws.batch.JobQueue(f"{self.project_stack}-queue",
            name=f"{self.project_stack}-queue",
            compute_environments=[create_env.arn],
            priority=1,
            state="ENABLED",
            tags=tags
        )

        CONTAINER_IMAGE = os.environ['CONTAINER_IMAGE']
        vcpu = self.max_vcpus
        memory = self.max_memory
        command = self.command

        lambda_execution_role = execution_role.arn.apply(lambda arn: arn)

        containerProperties = pulumi.Output.all(command, CONTAINER_IMAGE, memory, vcpu, lambda_execution_role).apply(
            lambda args: {
                "command": args[0],
                "image": args[1],
                "resourceRequirements": [
                    {"type": "MEMORY", "value": str(args[2])},
                    {"type": "VCPU", "value": str(args[3])}
                ],
                "executionRoleArn": args[4],
            }
        )
        jsonDef = containerProperties.apply(json.dumps)
        #jsonDef = json.dumps(containerProperties)

        definition = aws.batch.JobDefinition(
            f"{self.project_stack}-definition",
            name = f"{self.project_stack}-definition",
            type="container",
            platform_capabilities=["FARGATE"],
            container_properties=jsonDef,
            tags=tags
        )

        event_pattern = {
            "source": ["aws.batch"],
            "detail-type": ["Batch Job State Change"],
            "detail": {
            "status": ["SUCCEEDED", "FAILED"]
            }
        }

        rule = aws.cloudwatch.EventRule(
            f"{self.project_stack}-eventbridge-rule",
            name=f"{self.project_stack}-eventbridge-rule",
            schedule_expression=self.cron,
            state="ENABLED",
            #event_pattern=event_pattern,
            tags=tags
        )

        event_target = aws.cloudwatch.EventTarget(
            f"{self.project_stack}-event-target",
            rule=rule.name,
            arn=queue.arn,
            role_arn="arn:aws:iam::221871915463:role/ecsEventsRole",
            batch_target=cloudwatch.EventTargetBatchTargetArgs(
                job_definition=definition.arn,
                job_name=rule.name,
                job_attempts=1
                ),
        )