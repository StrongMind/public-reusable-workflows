import json
import os

import pulumi
import pulumi_aws as aws
import pulumi_awsx as awsx
from pulumi import Config, export, Output


class ContainerComponent(pulumi.ComponentResource):
    def __init__(self, name, opts=None, **kwargs):
        super().__init__('strongmind:global_build:commons:container', name, None, opts)

        self.container_image = kwargs.get('container_image')
        self.app_path = kwargs.get('app_path') or './'
        self.container_port = kwargs.get('container_port') or 3000
        self.cpu = kwargs.get('cpu') or 256
        self.memory = kwargs.get("memory") or 512
        self.env_vars = kwargs.get('env_vars', {})

        self.ecs_cluster = aws.ecs.Cluster("cluster",
                                           name=name,
                                           opts=pulumi.ResourceOptions(parent=self),
                                           )
        self.load_balancer = awsx.lb.ApplicationLoadBalancer("loadbalancer",
                                                             name=name,
                                                             default_target_group_port=self.container_port,
                                                             opts=pulumi.ResourceOptions(parent=self),
                                                             )

        task_definition_args = awsx.ecs.FargateServiceTaskDefinitionArgs(
                container=awsx.ecs.TaskDefinitionContainerDefinitionArgs(
                    image=self.container_image,
                    cpu=self.cpu,
                    memory=self.memory,
                    essential=True,
                    port_mappings=[awsx.ecs.TaskDefinitionPortMappingArgs(
                        container_port=self.container_port,
                        host_port=self.container_port,
                        target_group=self.load_balancer.default_target_group,
                    )],
                    environment=[{"name": k, "value": v} for k, v in self.env_vars.items()]
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
