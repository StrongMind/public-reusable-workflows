import os

import pulumi
import pulumi_aws as aws


class RedisComponent(pulumi.ComponentResource):
    def __init__(self, name, opts=None, **kwargs):
        super().__init__('strongmind:global_build:commons:redis', name, None, opts)
        self.kwargs = kwargs
        self.env_vars = self.kwargs.get('env_vars', {})
        self.node_type = self.kwargs.get('node_type', 'cache.t4g.small')
        self.num_cache_nodes = self.kwargs.get('num_cache_nodes', 1)

        self.env_name = os.environ.get('ENVIRONMENT_NAME', 'stage')

        project = pulumi.get_project()
        stack = pulumi.get_stack()
        project_stack = f"{project}-{stack}"

        self.tags = {
            "product": project,
            "repository": project,
            "service": project,
            "environment": self.env_name,
        }

        self.cluster = aws.elasticache.Cluster(
            "redis",
            cluster_id=project_stack,
            engine="redis",
            node_type=self.node_type,
            engine_version="7.0",
            num_cache_nodes=self.num_cache_nodes,
            parameter_group_name="default.redis7",
            port=6379,
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        self.register_outputs({})
