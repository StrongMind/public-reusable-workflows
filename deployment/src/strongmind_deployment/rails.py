import json

import pulumi
import pulumi_random as random
import pulumi_aws as aws
from pulumi import export, Output

from strongmind_deployment.container import ContainerComponent


class RailsComponent(pulumi.ComponentResource):
    def __init__(self, name, opts=None, **kwargs):
        super().__init__('strongmind:global_build:commons:rails', name, None, opts)
        self.db_password = None
        self.container = None
        self.rds_serverless_cluster_instance = None
        self.rds_serverless_cluster = None
        self.kwargs = kwargs

        self.rds(name)

        self.ecs(name)

        self.register_outputs({
            'rds_serverless_cluster': self.rds_serverless_cluster.cluster_identifier
        })

    def ecs(self, name):
        if 'env_vars' not in self.kwargs:
            self.kwargs['env_vars'] = {}

        self.kwargs['env_vars']['DATABASE_HOST'] = self.rds_serverless_cluster.endpoint
        self.kwargs['env_vars']['DB_USERNAME'] = self.rds_serverless_cluster.master_username
        self.kwargs['env_vars']['DB_PASSWORD'] = self.rds_serverless_cluster.master_password
        self.kwargs['env_vars']['DATABASE_URL'] = self.get_database_url()
        self.container = ContainerComponent(name,
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
            master_username=name.replace('-', '_'),
            master_password=self.db_password.result,
            opts=pulumi.ResourceOptions(parent=self),
            serverlessv2_scaling_configuration=aws.rds.ClusterServerlessv2ScalingConfigurationArgs(
                min_capacity=0.5,
                max_capacity=16,
            )
        )
        self.rds_serverless_cluster_instance = aws.rds.ClusterInstance(
            'rds_serverless_cluster_instance',
            identifier=name,
            cluster_identifier=self.rds_serverless_cluster.cluster_identifier,
            instance_class='db.serverless',
            engine=self.rds_serverless_cluster.engine,
            engine_version=self.rds_serverless_cluster.engine_version,
        )

        export("db_endpoint", Output.concat(self.rds_serverless_cluster.endpoint))

    def get_database_url(self):
        return Output.concat('postgres://',
                             self.rds_serverless_cluster.master_username,
                             ':',
                             self.rds_serverless_cluster.master_password,
                             '@',
                             self.rds_serverless_cluster.endpoint,
                             ':5432/',
                             self.rds_serverless_cluster.master_username)
