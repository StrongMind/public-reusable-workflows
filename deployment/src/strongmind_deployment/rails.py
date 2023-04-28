import json

import pulumi
import pulumi_random as random
import pulumi_aws as aws
from pulumi import export, Output

from strongmind_deployment.container import ContainerComponent


class RailsComponent(pulumi.ComponentResource):
    def __init__(self, name, opts=None, **kwargs):
        super().__init__('strongmind:global_build:commons:rails', name, None, opts)
        self.firewall_rule = None
        self.db_password = None
        self.container = None
        self.rds_serverless_cluster_instance = None
        self.rds_serverless_cluster = None
        self.kwargs = kwargs
        self.env_vars = self.kwargs.get('env_vars', {})

        project = pulumi.get_project()
        stack = pulumi.get_stack()
        self.tags = {
            "product": project,
            "repository": project,
            "service": project,
            "environment": self.env_vars.get("ENVIRONMENT_NAME", "stage"),
        }

        self.rds(stack)

        self.ecs(stack)

        self.security()

        self.register_outputs({})

    def security(self):
        container_security_group_id = self.kwargs.get(
            'container_security_group_id',
            self.container.fargate_service.service.network_configuration.security_groups[0])  # pragma: no cover

        self.firewall_rule = aws.ec2.SecurityGroupRule(
            'rds_security_group_rule',
            type='ingress',
            from_port=5432,
            to_port=5432,
            protocol='tcp',
            security_group_id=self.rds_serverless_cluster.vpc_security_group_ids[0],
            source_security_group_id=container_security_group_id,
            opts=pulumi.ResourceOptions(parent=self,
                                        depends_on=[self.rds_serverless_cluster_instance,
                                                    self.container])
        )

    def ecs(self, name):
        additional_env_vars = {
            'DATABASE_HOST': self.rds_serverless_cluster.endpoint,
            'DB_USERNAME': self.rds_serverless_cluster.master_username,
            'DB_PASSWORD': self.rds_serverless_cluster.master_password,
            'DATABASE_URL': self.get_database_url(),
            'RAILS_ENV': 'production'
        }

        self.env_vars.update(additional_env_vars)
        self.kwargs['env_vars'] = self.env_vars

        self.container = ContainerComponent("container",
                                            pulumi.ResourceOptions(parent=self),
                                            **self.kwargs
                                            )

    def rds(self, name):
        self.db_password = random.RandomPassword("password",
                                                 length=30,
                                                 special=False)
        self.rds_serverless_cluster = aws.rds.Cluster(
            'rds_serverless_cluster',
            cluster_identifier=name,
            engine='aurora-postgresql',
            engine_mode='provisioned',
            engine_version='15.2',
            database_name="app",
            master_username=name.replace('-', '_'),
            master_password=self.db_password.result,
            serverlessv2_scaling_configuration=aws.rds.ClusterServerlessv2ScalingConfigurationArgs(
                min_capacity=0.5,
                max_capacity=16,
            ),
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )
        self.rds_serverless_cluster_instance = aws.rds.ClusterInstance(
            'rds_serverless_cluster_instance',
            identifier=name,
            cluster_identifier=self.rds_serverless_cluster.cluster_identifier,
            instance_class='db.serverless',
            engine=self.rds_serverless_cluster.engine,
            engine_version=self.rds_serverless_cluster.engine_version,
            publicly_accessible=True,
            opts=pulumi.ResourceOptions(parent=self, depends_on=[self.rds_serverless_cluster]),
        )

        export("db_endpoint", Output.concat(self.rds_serverless_cluster.endpoint))

    def get_database_url(self):
        return Output.concat('postgres://',
                             self.rds_serverless_cluster.master_username,
                             ':',
                             self.rds_serverless_cluster.master_password,
                             '@',
                             self.rds_serverless_cluster.endpoint,
                             ':5432/app')
