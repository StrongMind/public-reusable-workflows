import os
import subprocess

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
        self.namespace = self.kwargs.get('namespace', f"{project}-{stack}")

        path = subprocess.check_output(['git', 'rev-parse', '--show-toplevel']).decode('utf-8').strip()
        file_path = f"{path}/CODEOWNERS"
        with open(file_path, 'r') as file:
            owning_team = [line.strip().split('@')[-1] for line in file if '@' in line][-1].split('/')[1]

        self.tags = {
            "product": project,
            "repository": project,
            "service": project,
            "environment": self.env_name,
            "owner": owning_team,
        }
        dependencies = []
        if hasattr(self, 'parameter_group'):
            dependencies.append(self.parameter_group)
        if 'namespace' in self.kwargs:
            cluster_id = name
        else:
            cluster_id = f"{self.namespace}-{name}"
        self.cluster = aws.elasticache.Cluster(
            name,
            cluster_id=cluster_id,
            engine="redis",
            node_type=self.node_type,
            engine_version="7.0",
            num_cache_nodes=self.num_cache_nodes,
            parameter_group_name=self.parameter_group_name,
            port=6379,
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self, depends_on=dependencies),
        )

        self.register_outputs({})

    @property
    def url(self):
        return Output.concat("redis://", self.cluster.cache_nodes[0].address, ":6379")


class QueueComponent(RedisComponent):
    def __init__(self, name, opts=None, **kwargs):
        project = pulumi.get_project()
        stack = pulumi.get_stack()
        namespace = kwargs.get('namespace', f"{project}-{stack}")
        kwargs['parameter_group_name'] = f"{namespace}-queue-redis7"
        self.parameter_group = aws.elasticache.ParameterGroup(
            f"{name}-parameter-group",
            name=kwargs['parameter_group_name'],
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
        project = pulumi.get_project()
        stack = pulumi.get_stack()
        namespace = kwargs.get('namespace', f"{project}-{stack}")
        kwargs['parameter_group_name'] = f"{namespace}-cache-redis7"
        self.parameter_group = aws.elasticache.ParameterGroup(
            f"{name}-parameter-group",
            name=kwargs['parameter_group_name'],
            family="redis7",
            parameters=[
                aws.elasticache.ParameterGroupParameterArgs(
                    name="maxmemory-policy",
                    value="allkeys-lru")
            ]
        )
        super().__init__(name, opts, **kwargs)
