import json
import os

import pulumi
import pulumi_aws as aws
import pulumi_awsx as awsx
from pulumi import Config, export, Output


class ContainerComponent(pulumi.ComponentResource):
    def __init__(self, name, opts=None, **kwargs):
        super().__init__('strongmind:global_build:commons:container', name, None, opts)

        self.app_path = kwargs.get('app_path') or './'
        self.container_port = kwargs.get('container_port') or 3000
        self.cpu = kwargs.get('cpu') or 256
        self.memory = kwargs.get("memory") or 512

        self.ecs_cluster = aws.ecs.Cluster("cluster",
                                           name=name,
                                           opts=pulumi.ResourceOptions(parent=self),
                                           )
        self.load_balancer = awsx.lb.ApplicationLoadBalancer("loadbalancer",
                                                             name=name,
                                                             opts=pulumi.ResourceOptions(parent=self),
                                                             )
        self.repo = awsx.ecr.Repository("repo",
                                        name=name,
                                        force_delete=True,
                                        opts=pulumi.ResourceOptions(parent=self),
                                        )

        image_name = os.getenv('IMAGE_TAG', f'{name}:latest')
        task_definition_args = awsx.ecs.FargateServiceTaskDefinitionArgs(
                container=awsx.ecs.TaskDefinitionContainerDefinitionArgs(
                    image=pulumi.Output.concat(self.repo.url, f"/{image_name}"),
                    cpu=self.cpu,
                    memory=self.memory,
                    essential=True,
                    port_mappings=[awsx.ecs.TaskDefinitionPortMappingArgs(
                        container_port=self.container_port,
                        host_port=self.container_port,
                        target_group=self.load_balancer.default_target_group,
                    )],
                )
            )

        self.fargate_service = awsx.ecs.FargateService(
            "service",
            name=f"{name}-service",
            cluster=self.ecs_cluster.arn,
            assign_public_ip=True,
            task_definition_args=task_definition_args,
            opts=pulumi.ResourceOptions(parent=self),
        )

        export("url", Output.concat("http://", self.load_balancer.load_balancer.dns_name))
        self.register_outputs({})
