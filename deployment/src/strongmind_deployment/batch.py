import pulumi 
import pulumi_aws as aws
import pulumi_awsx as awsx
import json
import os
import subprocess

class BatchComponent(pulumi.ComponentResource):
    def __init__(self, name, **kwargs):
        #super().__init__("custom:module:BatchComponent", name, {})
        self.env_name = os.environ.get('ENVIRONMENT_NAME', 'stage')
        self.kwargs = kwargs
        self.name = name
        self.max_vcpus = kwargs.get('max_vcpus', None)
        #self.image_id = image_id
        self.service_role = kwargs.get('service_role', None)
        self.priority = kwargs.get('priority', None)
        self.json = json


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

        default_vpc_resource = awsx.ec2.DefaultVpc("defaultVpcResource")
        default_vpc_id = default_vpc_resource.vpc_id
        """default_security_group_resource = aws.ec2.DefaultSecurityGroup("default",
            ingress=[aws.ec2.DefaultSecurityGroupIngressArgs(
            from_port=0,
            protocol="string",
            to_port=0,
            cidr_blocks=["0.0.0.0/0"],
            description="string",
            prefix_list_ids=["string"],
            security_groups=["string"],
            self=False,
            )],
            revoke_rules_on_delete=False,
            tags={
                "string": "string",
            },
            vpc_id=default_vpc_id,
        )"""

        default_vpc = aws.ec2.get_vpc(default=True)
        default_security_group_resource = aws.ec2.get_security_groups(filters=[
            aws.ec2.GetSecurityGroupsFilterArgs(
                name="group-name",
                values=["*nodes*"],
            ),
            aws.ec2.GetSecurityGroupsFilterArgs(
                name="vpc-id",
                values=[default_vpc_id],
            ),
        ])
        print(default_security_group_resource.ids)
        #for dirattr in dir(default_security_group_resource):
            #print(f" attr is {dirattr} and the type is {type(dirattr)}")
        #exit()
        default_subnet = default_vpc_resource.public_subnet_ids[0]

        create_env = aws.batch.ComputeEnvironment(f"{name}-batch",
        compute_environment_name=f"{name}-batch",
        compute_resources=aws.batch.ComputeEnvironmentComputeResourcesArgs( max_vcpus=self.max_vcpus,
            security_group_ids=[default_security_group_resource.id],
            subnets=[default_subnet],
            type="FARGATE",
            ),
        type="MANAGED",
        tags=tags,
        service_role=self.service_role
        ) 

        definition = aws.batch.JobDefinition(
            f"{name}-definition",
            type="container",
            platform_capabilities=["FARGATE"],
            container_properties=json
        )

        sch_policy = aws.batch.SchedulingPolicy(f"{name}-sch_policy",
         fair_share_policy=aws.batch.SchedulingPolicyFairSharePolicyArgs(
             share_distributions=[
                 aws.batch.SchedulingPolicyFairSharePolicyShareDistributionArgs(
                     share_identifier="*",
                     weight_factor=1
                    )
                ]
            ),
            tags=tags
        )

        queue = aws.batch.JobQueue(f"{name}-queue",
            compute_environments=[create_env],
            priority=self.priority,
            state="ENABLED",
            tags=tags
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

        aws.cloudwatch.EventTarget(
            f"{name}-event-target",
            rule=rule.name,
            arn=queue.arn,
        )
        
        ecr_repo = aws.ecr.Repository(
            f"{name}-ecr-repo",
            image_scanning_configuration=aws.ecr.RepositoryImageScanningConfigurationArgs(
                scan_on_push=True
            ),
            tags=tags
        )
