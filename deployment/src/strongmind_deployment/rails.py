import json

import pulumi
import pulumi_aws as aws

from strongmind_deployment.container import ContainerComponent


class RailsComponent(pulumi.ComponentResource):
    def __init__(self, name, opts=None, **kwargs):
        super().__init__('strongmind:global_build:commons:rails', name, None, opts)
        self.kwargs = kwargs

        self.rds(name)

        self.ecs(name)

        self.register_outputs({
            'rds_serverless_cluster': self.rds_serverless_cluster.cluster_identifier
        })

    def ecs(self, name):
        self.container = ContainerComponent(name,
                                            pulumi.ResourceOptions(parent=self),
                                            **self.kwargs
                                            )

    def rds(self, name):
        self.rds_serverless_cluster = aws.rds.Cluster(
            'rds_serverless_cluster',
            cluster_identifier=name,
            engine='aurora-postgresql',
            engine_mode='provisioned',
            engine_version='15.2',
            master_username=name.replace('-', '_'),
            master_password="blahblahblah",
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
