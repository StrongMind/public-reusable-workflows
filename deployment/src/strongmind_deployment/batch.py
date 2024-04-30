import pulumi 
import pulumi_aws as aws
import pulumi_awsx as awsx
import json
import os
import subprocess
from pulumi_aws import cloudwatch

class BatchComponent(pulumi.ComponentResource):
    def __init__(self, name, **kwargs):
        #super().__init__("custom:module:BatchComponent", name, {})
        self.env_name = os.environ.get('ENVIRONMENT_NAME', 'stage')
        self.kwargs = kwargs
        self.name = name
        self.max_vcpus = kwargs.get('max_vcpus', None)
        #self.image_id = image_id
        self.service_role = kwargs.get('service_role', None)
        priority = 1
        #self.json = json


        stack = pulumi.get_stack()
        region = "us-west-2"
        config = pulumi.Config()
        project = pulumi.get_project()

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
        create_env = aws.batch.ComputeEnvironment(f"{name}-batch",
        compute_environment_name=f"{name}-batch",
        compute_resources=aws.batch.ComputeEnvironmentComputeResourcesArgs( max_vcpus=self.max_vcpus,
            security_group_ids=default_sec_group,
            subnets=default_subnets.ids,
            type="FARGATE",
            ),
        type="MANAGED",
        tags=tags,
        service_role=self.service_role
        ) 


        sch_policy = aws.batch.SchedulingPolicy(f"{name}-sch_policy",
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

        queue = aws.batch.JobQueue(f"{name}-queue",
            compute_environments=[create_env.arn],
            priority=priority,
            state="ENABLED",
            tags=tags
        )

        CONTAINER_IMAGE = os.environ['CONTAINER_IMAGE']
        vcpu = 0.25
        memory = 2048

        containerProperties = {
            "command": ["echo", "hello world"],
            "image": CONTAINER_IMAGE,
            "resourceRequirements": [
                {"type": "MEMORY", "value": str(memory)},
                {"type": "VCPU", "value": str(vcpu)}
            ],
            "executionRoleArn": "arn:aws:iam::221871915463:role/ecsTaskExecutionRole",
            "jobRoleArn": "arn:aws:iam::221871915463:role/ecsTaskExecutionRole",
        }

        jsonDef = json.dumps(containerProperties)

        definition = aws.batch.JobDefinition(
            f"{name}-definition",
            type="container",
            platform_capabilities=["FARGATE"],
            container_properties=jsonDef
        )

        schedule_expression = "cron(0 0 * * ? *)"
        event_pattern = {
            "source": ["aws.batch"],
            "detail-type": ["Batch Job State Change"],
            "detail": {
            "status": ["SUCCEEDED", "FAILED"]
            }
        }

        rule = aws.cloudwatch.EventRule(
            f"{name}-eventbridge-rule",
            schedule_expression=schedule_expression,
            state="ENABLED",
            #event_pattern=event_pattern,
            tags=tags
        )

        event_target = aws.cloudwatch.EventTarget(
            f"{name}-event-target",
            rule=rule.name,
            arn=queue.arn,
            role_arn="arn:aws:iam::221871915463:role/ecsEventsRole",
            batch_target=cloudwatch.EventTargetBatchTargetArgs(
                job_definition=definition,
                job_name=rule.name,
                job_attempts=1
                ),
        )
        
        ecr_repo = aws.ecr.Repository(
            f"{name}-ecr-repo",
            image_scanning_configuration=aws.ecr.RepositoryImageScanningConfigurationArgs(
                scan_on_push=True
            ),
            tags=tags
        )
