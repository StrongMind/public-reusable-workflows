import time

import boto3
import pulumi


class ExecutionResourceProvider(pulumi.dynamic.ResourceProvider):
    def __init__(self, cluster, family, subnets, security_groups):
        self.cluster = cluster
        self.family = family
        self.subnets = subnets
        self.security_groups = security_groups

    def create(self, inputs):
        output = self.run_task()
        return pulumi.dynamic.CreateResult(id_="0", outs={"output": output})

    def update(self, id, _olds, props):
        output = self.run_task()
        return pulumi.dynamic.UpdateResult(outs={"output": output})

    def diff(self, _id: str, _olds, _news):
        # Show that this has "changed" so that it runs every time
        return pulumi.dynamic.DiffResult(changes=True)

    def run_task(self):
        # Run ECS task with boto3
        client = boto3.client('ecs')
        response = client.run_task(
            cluster=self.cluster,
            taskDefinition=self.family,
            launchType='FARGATE',
            networkConfiguration={
                'awsvpcConfiguration': {
                    'subnets': self.subnets,
                    'securityGroups': self.security_groups,
                    'assignPublicIp': 'ENABLED'
                }
            },
            startedBy='rails-component'
        )
        task_arn = response['tasks'][0]['taskArn']
        task_id = task_arn.split('/')[-1]
        task = client.describe_tasks(
            cluster=self.cluster,
            tasks=[task_id]
        )
        while task['tasks'][0]['lastStatus'] != 'STOPPED':
            time.sleep(5)
            task = client.describe_tasks(
                cluster=self.cluster,
                tasks=[task_id]
            )
        exit_code = task['tasks'][0]['containers'][0]['exitCode']
        if exit_code:
            raise Exception(f"Task exited with code {exit_code}")
        return True


class ExecutionComponent(pulumi.dynamic.Resource):
    def __init__(self, name: str, cluster, family, subnets, security_groups, props={}, opts=None):
        super().__init__(ExecutionResourceProvider(cluster, family, subnets, security_groups), name, props, opts)
