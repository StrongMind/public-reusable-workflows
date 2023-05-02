import json
import os
import re

import pulumi
import pulumi_aws as aws
import pulumi_awsx as awsx
from pulumi import Config, export, Output
from pulumi_cloudflare import get_zone, Record


class ContainerComponent(pulumi.ComponentResource):
    def __init__(self, name, opts=None, **kwargs):
        super().__init__('strongmind:global_build:commons:container', name, None, opts)

        self.cert_validation_cert = None
        self.cert_validation_record = None
        self.cert = None
        self._security_group_name = None
        self.cname_record = None
        self.container_image = kwargs.get('container_image')
        self.app_path = kwargs.get('app_path') or './'
        self.container_port = kwargs.get('container_port') or 3000
        self.cpu = kwargs.get('cpu') or 256
        self.memory = kwargs.get("memory") or 512
        self.env_vars = kwargs.get('env_vars', {})
        self.kwargs = kwargs
        self.env_name = os.environ.get('ENVIRONMENT_NAME', 'stage')

        stack = pulumi.get_stack()
        project = pulumi.get_project()
        project_stack = f"{project}-{stack}"

        self.tags = {
            "product": project,
            "repository": project,
            "service": project,
            "environment": self.env_name,
        }

        self.ecs_cluster = aws.ecs.Cluster("cluster",
                                           name=project_stack,
                                           tags=self.tags,
                                           opts=pulumi.ResourceOptions(parent=self),
                                           )
        self.load_balancer = awsx.lb.ApplicationLoadBalancer(
            "loadbalancer",
            name=project_stack,
            default_target_group_port=self.container_port,
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        self.dns(project)

        load_balancer_arn = kwargs.get('load_balancer_arn', self.load_balancer.load_balancer.arn)
        target_group_arn = kwargs.get('target_group_arn', self.load_balancer.default_target_group.arn)
        self.load_balancer_listener = aws.lb.Listener(
            "listener443",
            load_balancer_arn=load_balancer_arn,
            certificate_arn=self.cert.arn,
            port=443,
            protocol="HTTPS",
            default_actions=[
                aws.lb.ListenerDefaultActionArgs(
                    type="forward",
                    target_group_arn=target_group_arn
                )],
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self,
                                        depends_on=[
                                            self.cert,
                                            self.cert_validation_record,
                                            self.cert_validation_cert,
                                        ]),
        )
        self.load_balancer_listener_redirect_http_to_https = aws.lb.Listener(
            "listener80",
            load_balancer_arn=load_balancer_arn,
            port=80,
            protocol="HTTP",
            default_actions=[aws.lb.ListenerDefaultActionArgs(
                type="redirect",
                redirect=aws.lb.ListenerDefaultActionRedirectArgs(
                    port="443",
                    protocol="HTTPS",
                    status_code="HTTP_301",
                ),
            )],
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        logs = aws.cloudwatch.LogGroup(
            f'log',
            retention_in_days=14,
            name=f'/aws/ecs/{project_stack}',
            tags=self.tags
        )
        task_definition_args = awsx.ecs.FargateServiceTaskDefinitionArgs(
            skip_destroy=True,
            family=project_stack,
            container=awsx.ecs.TaskDefinitionContainerDefinitionArgs(
                name=project_stack,
                log_configuration=awsx.ecs.TaskDefinitionLogConfigurationArgs(
                    log_driver="awslogs",
                    options={
                        "awslogs-group": logs.name,
                        "awslogs-region": "us-west-2",
                        "awslogs-stream-prefix": "container",
                    },
                ),
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
            name=project_stack,
            cluster=self.ecs_cluster.arn,
            continue_before_steady_state=True,
            assign_public_ip=True,
            task_definition_args=task_definition_args,
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        self.register_outputs({})

    def dns(self, name):
        if self.env_name != "prod":
            name = f"{self.env_name}-{name}"
        domain = 'strongmind.com'
        full_name = f"{name}.{domain}"
        zone_id = self.kwargs.get('zone_id', 'b4b7fec0d0aacbd55c5a259d1e64fff5')
        lb_dns_name = self.kwargs.get('load_balancer_dns_name',
                                      self.load_balancer.load_balancer.dns_name)  # pragma: no cover
        self.cname_record = Record(
            'cname_record',
            name=name,
            type='CNAME',
            zone_id=zone_id,
            value=lb_dns_name,
            ttl=1,
            opts=pulumi.ResourceOptions(parent=self),
        )
        pulumi.export("url", Output.concat("https://", full_name))

        self.cert = aws.acm.Certificate(
            "cert",
            domain_name=full_name,
            validation_method="DNS",
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )
        domain_validation_options = self.kwargs.get('domain_validation_options',
                                                    self.cert.domain_validation_options)  # pragma: no cover

        resource_record_value = domain_validation_options[0].resource_record_value

        def remove_trailing_period(value):
            return re.sub("\\.$", "", value)

        if type(resource_record_value) != str:
            resource_record_value = resource_record_value.apply(remove_trailing_period)

        self.cert_validation_record = Record(
            'cert_validation_record',
            name=domain_validation_options[0].resource_record_name,
            type=domain_validation_options[0].resource_record_type,
            zone_id=zone_id,
            value=resource_record_value,
            ttl=1,
            opts=pulumi.ResourceOptions(parent=self, depends_on=[self.cert,
                                                                 self.cname_record]),
        )

        self.cert_validation_cert = aws.acm.CertificateValidation(
            "cert_validation",
            certificate_arn=self.cert.arn,
            validation_record_fqdns=[self.cert_validation_record.hostname],
            opts=pulumi.ResourceOptions(parent=self, depends_on=[self.cert_validation_record]),
        )
