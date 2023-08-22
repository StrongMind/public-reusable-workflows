import time
from typing import Optional

import boto3
import pulumi
from pulumi import ResourceOptions


class ExecutionResourceInputs:
    cluster: pulumi.Input[str]
    family: pulumi.Input[str]
    subnets: pulumi.Input[str]
    security_groups: pulumi.Input[str]
    ecs_client: pulumi.Input[boto3.client]

    def __init__(self, cluster, family, subnets, security_groups, ecs_client=None):
        self.cluster = cluster
        self.family = family
        self.subnets = subnets
        self.security_groups = security_groups
        self.ecs_client = ecs_client


class _ExecutionResourceProviderInputs:
    cluster: str
    family: str
    subnets: str
    security_groups: str
    ecs_client: boto3.client

    def __init__(self, cluster, family, subnets, security_groups, ecs_client=None):
        self.cluster = cluster
        self.family = family
        self.subnets = subnets
        self.security_groups = security_groups
        self.ecs_client = ecs_client


class ExecutionResourceProvider(pulumi.dynamic.ResourceProvider):
    ecs_client: boto3.client

    def create(self, props):
        self.ecs_client = props.get('ecs_client', boto3.client('ecs'))
        output = self.run_task(props)
        return pulumi.dynamic.CreateResult(id_="0", outs={"output": output})

    def update(self, id, _olds, props):
        self.ecs_client = props.get('ecs_client', boto3.client('ecs'))
        output = self.run_task(props)
        return pulumi.dynamic.UpdateResult(outs={"output": output})

    def diff(self, _id: str, _olds, _news):
        # Show that this has "changed" so that it runs every time
        return pulumi.dynamic.DiffResult(changes=True)

    #
    def run_task(self, inputs):
        response = self.ecs_client.run_task(
            taskDefinition=inputs['family'],
            cluster=inputs['cluster'],
            launchType='FARGATE',
            networkConfiguration={
                'awsvpcConfiguration': {
                    'subnets': inputs['subnets'],
                    'securityGroups': inputs['security_groups'],
                    'assignPublicIp': 'ENABLED'
                }
            },
            startedBy='rails-component'
        )
        task_arn = response['tasks'][0]['taskArn']
        task_id = task_arn.split('/')[-1]
        task = self.ecs_client.describe_tasks(
            cluster=inputs['cluster'],
            tasks=[task_id]
        )
        while task['tasks'][0]['lastStatus'] != 'STOPPED':
            time.sleep(5)
            task = self.ecs_client.describe_tasks(
                cluster=inputs['cluster'],
                tasks=[task_id]
            )
        exit_code = task['tasks'][0]['containers'][0]['exitCode']
        if exit_code:
            raise Exception(f"Task exited with code {exit_code}")
        return True


class ExecutionComponent(pulumi.dynamic.Resource):
    def __init__(self, name: str, props: ExecutionResourceInputs, opts: Optional[ResourceOptions] = None):
        super().__init__(ExecutionResourceProvider(), name, {**vars(props)}, opts)
