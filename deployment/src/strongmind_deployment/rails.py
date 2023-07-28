import json
import os

import pulumi
import pulumi_random as random
import pulumi_aws as aws
from pulumi import export, Output

from strongmind_deployment.container import ContainerComponent
from strongmind_deployment.redis import RedisComponent, QueueComponent, CacheComponent
from strongmind_deployment.secretsmanager import SecretsComponent


def sidekiq_present():  # pragma: no cover
    return os.path.exists('../Gemfile') and 'sidekiq' in open('../Gemfile').read()


class RailsComponent(pulumi.ComponentResource):

    def __init__(self, name, opts=None, **kwargs):
        """
        Resource that produces a Rails application running on AWS Fargate.

        :param name: The _unique_ name of the resource.
        :param opts: A bag of optional settings that control this resource's behavior.
        :key env_vars: A dictionary of environment variables to pass to the Rails application.
        :key queue_redis: Either True to create a default queue Redis instance or a RedisComponent to use. Defaults to True if sidekiq is in the Gemfile.
        :key cache_redis: Either True to create a default cache Redis instance or a RedisComponent to use.
        :key web_entry_point: The entry point for the web container. Defaults to `["sh", "-c",
                                                                                "rails db:prepare db:migrate db:seed && "
                                                                                "rails assets:precompile && "
                                                                                "rails server --port 3000 -b 0.0.0.0"]`
        :key need_worker: Whether to create a worker container. Defaults to True if sidekiq is in the Gemfile.
        :key worker_entry_point: The entry point for the worker container. Defaults to `["sh", "-c", "bundle exec sidekiq"]`
        :key cpu: The number of CPU units to reserve for the web container. Defaults to 256.
        :key memory: The amount of memory (in MiB) to allow the web container to use. Defaults to 512.
        :key app_path: The path to the Rails application for the web. Defaults to `./`.
        :key worker_cpu: The number of CPU units to reserve for the worker container. Defaults to 256.
        :key worker_memory: The amount of memory (in MiB) to allow the worker container to use. Defaults to 512.
        :key worker_app_path: The path to the Rails application for the worker. Defaults to `./`.
        :key dynamo_tables: A list of DynamoDB tables to create. Defaults to `[]`. Each table is a DynamoComponent.
        """
        super().__init__('strongmind:global_build:commons:rails', name, None, opts)
        self.need_worker = None
        self.cname_record = None
        self.firewall_rule = None
        self.db_password = None
        self.web_container = None
        self.worker_container = None
        self.secret = None
        self.rds_serverless_cluster_instance = None
        self.rds_serverless_cluster = None
        self.kwargs = kwargs
        self.dynamo_tables = self.kwargs.get('dynamo_tables', [])
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

        self.setup_dynamo()

        self.setup_redis()

        self.secrets()

        self.ecs()

        self.security()

        self.register_outputs({})

    def setup_redis(self):
        if sidekiq_present():
            self.env_vars['REDIS_PROVIDER'] = 'QUEUE_REDIS_URL'
            if 'queue_redis' not in self.kwargs:
                self.kwargs['queue_redis'] = True
        if 'queue_redis' in self.kwargs:
            if isinstance(self.kwargs['queue_redis'], RedisComponent):
                self.queue_redis = self.kwargs['queue_redis']
            elif self.kwargs['queue_redis']:
                self.queue_redis = QueueComponent("queue-redis")

            if self.queue_redis:
                self.env_vars['QUEUE_REDIS_URL'] = self.queue_redis.url
        if 'cache_redis' in self.kwargs:
            if isinstance(self.kwargs['cache_redis'], RedisComponent):
                self.cache_redis = self.kwargs['cache_redis']
            elif self.kwargs['cache_redis']:
                self.cache_redis = CacheComponent("cache-redis")

            if self.cache_redis:
                self.env_vars['CACHE_REDIS_URL'] = self.cache_redis.url

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
        self.kwargs['secrets'] = self.secret.get_secrets(self.secret.sm_secret.arn)

        self.web_container = ContainerComponent("container",
                                                pulumi.ResourceOptions(parent=self),
                                                **self.kwargs
                                                )

        self.need_worker = self.kwargs.get('need_worker', None)
        if self.need_worker is None:  # pragma: no cover
            # If we don't know if we need a worker, check for sidekiq in the Gemfile
            self.need_worker = sidekiq_present()

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
        self.kwargs['secrets'] = self.secret.get_secrets(self.secret.sm_secret.arn)
        self.worker_container = ContainerComponent("worker",
                                                   pulumi.ResourceOptions(parent=self),
                                                   **self.kwargs
                                                   )
    
    def secrets(self):
        self.secret = SecretsComponent("secrets",
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

    def setup_dynamo(self):
        for table_component in self.dynamo_tables:
            env_var_name = table_component._name.upper() + '_DYNAMO_TABLE_NAME'
            self.env_vars[env_var_name] = table_component.table.name

