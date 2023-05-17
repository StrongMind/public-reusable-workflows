import json
import os

import pulumi
import pulumi_random as random
import pulumi_aws as aws
from pulumi import export, Output

from strongmind_deployment.container import ContainerComponent
from strongmind_deployment.redis import RedisComponent


class RailsComponent(pulumi.ComponentResource):
    def __init__(self, name, opts=None, **kwargs):
        super().__init__('strongmind:global_build:commons:rails', name, None, opts)
        self.need_worker = None
        self.cname_record = None
        self.firewall_rule = None
        self.db_password = None
        self.web_container = None
        self.worker_container = None
        self.rds_serverless_cluster_instance = None
        self.rds_serverless_cluster = None
        self.kwargs = kwargs
        self.env_vars = self.kwargs.get('env_vars', {})

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

        self.rds(project_stack)

        self.redis = RedisComponent("redis",
                                    env_vars=self.env_vars)
        export("redis_endpoint", Output.concat(self.redis.cluster.cache_nodes[0]['address']))

        self.ecs()

        self.security()

        self.register_outputs({})

    def security(self):
        container_security_group_id = self.kwargs.get(
            'container_security_group_id',
            self.web_container.fargate_service.service.network_configuration.security_groups[0])  # pragma: no cover

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
                                                    self.web_container])
        )

    def ecs(self):
        container_image = os.environ['CONTAINER_IMAGE']
        master_key = os.environ['RAILS_MASTER_KEY']
        additional_env_vars = {
            'RAILS_MASTER_KEY': master_key,
            'DATABASE_HOST': self.rds_serverless_cluster.endpoint,
            'DB_USERNAME': self.rds_serverless_cluster.master_username,
            'DB_PASSWORD': self.rds_serverless_cluster.master_password,
            'DATABASE_URL': self.get_database_url(),
            'REDIS_URL': self.get_redis_endpoint(),
            'RAILS_ENV': 'production'
        }

        self.env_vars.update(additional_env_vars)
        self.kwargs['env_vars'] = self.env_vars
        self.kwargs['container_image'] = container_image

        web_entry_point = self.kwargs.get('web_entry_point', ["sh", "-c",
                                                              "rails db:prepare db:migrate db:seed && "
                                                              "rails assets:precompile && "
                                                              "rails server --port 3000 -b 0.0.0.0"])

        self.kwargs['entry_point'] = web_entry_point

        self.web_container = ContainerComponent("container",
                                                pulumi.ResourceOptions(parent=self),
                                                **self.kwargs
                                                )

        self.need_worker = self.kwargs.get('need_worker', None)
        if self.need_worker is None:
            # If we don't know if we need a worker, check for sidekiq in the Gemfile
            self.need_worker = os.path.exists('../Gemfile') and 'sidekiq' in open('../Gemfile').read()

        if self.need_worker:
            self.setup_worker()

    def setup_worker(self):
        worker_entry_point = self.kwargs.get('worker_entry_point', ["sh", "-c", "bundle exec sidekiq"])
        self.kwargs['entry_point'] = worker_entry_point
        self.kwargs['cpu'] = self.kwargs.get('worker_cpu')
        self.kwargs['memory'] = self.kwargs.get('worker_memory')
        self.kwargs['app_path'] = self.kwargs.get('worker_app_path')
        self.kwargs['need_load_balancer'] = False
        self.kwargs['ecs_cluster_arn'] = self.web_container.ecs_cluster_arn
        self.worker_container = ContainerComponent("worker",
                                                   pulumi.ResourceOptions(parent=self),
                                                   **self.kwargs
                                                   )

    def rds(self, project_stack):
        self.db_password = random.RandomPassword("password",
                                                 length=30,
                                                 special=False)
        self.rds_serverless_cluster = aws.rds.Cluster(
            'rds_serverless_cluster',
            cluster_identifier=project_stack,
            engine='aurora-postgresql',
            engine_mode='provisioned',
            engine_version='15.2',
            database_name="app",
            master_username=project_stack.replace('-', '_'),
            master_password=self.db_password.result,
            serverlessv2_scaling_configuration=aws.rds.ClusterServerlessv2ScalingConfigurationArgs(
                min_capacity=0.5,
                max_capacity=16,
            ),
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self,
                                        protect=True),
        )
        self.rds_serverless_cluster_instance = aws.rds.ClusterInstance(
            'rds_serverless_cluster_instance',
            identifier=project_stack,
            cluster_identifier=self.rds_serverless_cluster.cluster_identifier,
            instance_class='db.serverless',
            engine=self.rds_serverless_cluster.engine,
            engine_version=self.rds_serverless_cluster.engine_version,
            publicly_accessible=True,
            opts=pulumi.ResourceOptions(parent=self,
                                        depends_on=[self.rds_serverless_cluster],
                                        protect=True),
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

    def get_redis_endpoint(self):
        return Output.concat('redis://',
                             self.redis.cluster.cache_nodes[0]['address'],
                             ':6379')
