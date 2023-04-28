import json
import os

import pulumi
import pulumi_aws as aws
import pulumi_awsx as awsx
from pulumi import Config, export, Output


class ContainerComponent(pulumi.ComponentResource):
    def __init__(self, name, opts=None, **kwargs):
        super().__init__('strongmind:global_build:commons:container', name, None, opts)

        self._security_group_name = None
        self.container_image = kwargs.get('container_image')
        self.app_path = kwargs.get('app_path') or './'
        self.container_port = kwargs.get('container_port') or 3000
        self.cpu = kwargs.get('cpu') or 256
        self.memory = kwargs.get("memory") or 512
        self.env_vars = kwargs.get('env_vars', {})

        stack = pulumi.get_stack()
        project = pulumi.get_project()
        self.tags = {
            "product": project,
            "repository": project,
            "service": project,
            "environment": self.env_vars.get("ENVIRONMENT_NAME", "stage"),
        }

        self.ecs_cluster = aws.ecs.Cluster("cluster",
                                           name=stack,
                                           tags=self.tags,
                                           opts=pulumi.ResourceOptions(parent=self),
                                           )
        self.load_balancer = awsx.lb.ApplicationLoadBalancer(
            "loadbalancer",
            name=stack,
            default_target_group_port=self.container_port,
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        load_balancer_arn = kwargs.get('load_balancer_arn', self.load_balancer.load_balancer.arn)
        target_group_arn = kwargs.get('target_group_arn', self.load_balancer.default_target_group.arn)
        self.load_balancer_listener = aws.lb.Listener("listener80",
                                                      port=80,
                                                      protocol="HTTP",
                                                      load_balancer_arn=load_balancer_arn,
                                                      # port=443,
                                                      # protocol="HTTPS",
                                                      default_actions=[
                                                          aws.lb.ListenerDefaultActionArgs(
                                                              type="forward",
                                                              target_group_arn=target_group_arn
                                                          )],
                                                      )
        # aws.lb.ListenerArgs(
        #     port=80,
        #     protocol="HTTP",
        #     default_action=awsx.lb.ApplicationListenerDefaultActionArgs(
        #         type="redirect",
        #         redirect=awsx.lb.ApplicationListenerDefaultActionRedirectArgs(
        #             port="443",
        #             protocol="HTTPS",
        #             status_code="HTTP_301",
        #         ),
        #     )
        # ),
        task_definition_args = awsx.ecs.FargateServiceTaskDefinitionArgs(
            skip_destroy=True,
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
            name=stack,
            cluster=self.ecs_cluster.arn,
            continue_before_steady_state=True,
            assign_public_ip=True,
            task_definition_args=task_definition_args,
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        export("url", Output.concat("http://", self.load_balancer.load_balancer.dns_name))
        self.register_outputs({})
