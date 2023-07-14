import os

import pulumi
import pulumi_aws as aws
from pulumi import Output


class RedisComponent(pulumi.ComponentResource):
    def __init__(self, name, opts=None, **kwargs):
        super().__init__('strongmind:global_build:commons:redis', name, None, opts)
        self.kwargs = kwargs
        self.env_vars = self.kwargs.get('env_vars', {})
        self.node_type = self.kwargs.get('node_type', 'cache.t4g.small')
        self.num_cache_nodes = self.kwargs.get('num_cache_nodes', 1)

        self.env_name = os.environ.get('ENVIRONMENT_NAME', 'stage')
        self.parameter_group_name = self.kwargs.get('parameter_group_name', 'default.redis7')

        project = pulumi.get_project()
        stack = pulumi.get_stack()

        self.tags = {
            "product": project,
            "repository": project,
            "service": project,
            "environment": self.env_name,
        }

        self.cluster = aws.elasticache.Cluster(
            "redis",
            cluster_id=f'{stack}-{name}',
            engine="redis",
            node_type=self.node_type,
            engine_version="7.0",
            num_cache_nodes=self.num_cache_nodes,
            parameter_group_name=self.parameter_group_name,
            port=6379,
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        self.register_outputs({})

    def get_url(self):
        return Output.concat("redis://", self.cluster.cache_nodes[0].address, ":6379")


class QueueComponent(RedisComponent):
    def __init__(self, name, opts=None, **kwargs):
        kwargs['parameter_group_name'] = f'{name}.queue.redis7'
        self.parameter_group = aws.elasticache.ParameterGroup(
            kwargs['parameter_group_name'],
            family="redis7",
            parameters=[
                aws.elasticache.ParameterGroupParameterArgs(
                    name="maxmemory-policy",
                    value="noeviction")
            ]
        )
        super().__init__(name, opts, **kwargs)


class CacheComponent(RedisComponent):
    def __init__(self, name, opts=None, **kwargs):
        kwargs['parameter_group_name'] = f'{name}.cache.redis7'
        self.parameter_group = aws.elasticache.ParameterGroup(
            kwargs['parameter_group_name'],
            family="redis7",
        )
        super().__init__(name, opts, **kwargs)
