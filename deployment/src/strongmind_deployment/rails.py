import hashlib
import os
import subprocess

import pulumi
import pulumi_aws as aws
import pulumi_random as random
from pulumi import export, Output
import boto3
from botocore.exceptions import ClientError

from strongmind_deployment import operations
from strongmind_deployment.container import ContainerComponent
from strongmind_deployment.execution import ExecutionComponent, ExecutionResourceInputs
from strongmind_deployment.redis import RedisComponent, QueueComponent, CacheComponent
from strongmind_deployment.secrets import SecretsComponent
from strongmind_deployment.storage import StorageComponent
from strongmind_deployment.dashboard import DashboardComponent
from strongmind_deployment.util import create_ecs_cluster, qualify_component_name


def sidekiq_present():  # pragma: no cover
    return os.path.exists('../Gemfile') and 'sidekiq' in open('../Gemfile').read()


class RailsComponent(pulumi.ComponentResource):

    def __init__(self, name, opts=None, **kwargs):
        """
        Resource that produces a Rails application running on AWS Fargate.

        :param name: The _unique_ name of the resource.
        :param opts: A bag of optional settings that control this resource's behavior.
        :key env_vars: A dictionary of environment variables to pass to the Rails application.
        :key namespace: A name to override the default naming of resources and DNS names.
        :key queue_redis: Either True to create a default queue Redis instance or a RedisComponent to use. Defaults to True if sidekiq is in the Gemfile.
        :key cache_redis: Either True to create a default cache Redis instance or a RedisComponent to use.
        :key execution_cmd: The command for the pre-deployment execution container. Defaults to `["sh", "-c",
                                      "bundle exec rails db:prepare db:migrate db:seed assets:precompile && echo 'Migrations complete'"]`.
        :key web_entry_point: The entry point for the web container. Defaults to the ENTRYPOINT in the Dockerfile.
        :key web_cmd: The command for the web container. Defaults to `["sh", "-c", "rails assets:precompile && rails server -b 0.0.0.0"]`.
        :key cpu: The number of CPU units to reserve for the web container. Defaults to 2048.
        :key memory: The amount of memory (in MiB) to allow the web container to use. Defaults to 4096.
        :key need_worker: Whether to create a worker container. Defaults to True if sidekiq is in the Gemfile.
        :key worker_entry_point: The entry point for the worker container. Defaults to the ENTRYPOINT in the Dockerfile. Requires need_worker to be True.
        :key worker_cmd: The command for the worker container. Defaults to `["sh", "-c", "bundle exec sidekiq"]`. Requires need_worker to be True.
        :key worker_cpu: The number of CPU units to reserve for the worker container. Defaults to 2048.
        :key worker_memory: The amount of memory (in MiB) to allow the worker container to use. Defaults to 4096.
        :key worker_log_metric_filters: A list of log metric filters to create for the worker container. Defaults to `[]`.
        :key dynamo_tables: A list of DynamoDB tables to create. Defaults to `[]`. Each table is a DynamoComponent.
        :key md5_hash_db_password: Whether to MD5 hash the database password. Defaults to False.
        :key storage: Whether to create an S3 bucket for the Rails application. Defaults to False.
        :key storage_private: Sets the bucket to public when false. Defaults to True.
        :key custom_health_check_path: The path to use for the health check. Defaults to `/up`.
        :key snapshot_identifier: The snapshot identifier to use for the RDS cluster. Defaults to None.
        :key kms_key_id: The KMS key ID to use for the RDS cluster. Defaults to None.
        :key db_name: The name of the database. Defaults to app.
        :key db_username: The username for connecting to the app database. Defaults to project name and environment.
        :key autoscale: Whether to autoscale the web container. Defaults to True.
        :key worker_autoscale: Whether to autoscale the worker container. Defaults to True.
        :key db_engine_version: The version of the database engine. Defaults to 15.4.
        :key desired_web_count: The number of instances of the web container to run. Defaults to 1.
        :key desired_worker_count: The number of instances of the worker container to run. Defaults to 1.
        :key rds_minimum_capacity: The minimum capacity of the RDS cluster. Defaults to 0.5.
        :key rds_maximum_capacity: The maximum capacity of the RDS cluster. Defaults to 16.
        """
        super().__init__('strongmind:global_build:commons:rails', name, None, opts)
        self.container_security_groups = None
        self.execution = None
        self.ecs_cluster = None
        self.migration_container = None
        self.queue_redis = None
        self.cache_redis = None
        self.storage = None
        self.storage_private = None
        self.need_worker = None
        self.cname_record = None
        self.firewall_rule = None
        self.db_username = None
        self.db_password = None
        self.db_name = None
        self.hashed_password = None
        self.web_container = None
        self.worker_container = None
        self.secret = None
        self.rds_serverless_cluster_instance = None
        self.rds_serverless_cluster = None
        self.kwargs = kwargs
        self.worker_log_metric_filters = self.kwargs.get('worker_log_metric_filters', [])
        self.snapshot_identifier = self.kwargs.get('snapshot_identifier', None)
        self.kms_key_id = self.kwargs.get('kms_key_id', None)
        self.dynamo_tables = self.kwargs.get('dynamo_tables', [])
        self.env_vars = self.kwargs.get('env_vars', {})
        self.autoscale = self.kwargs.get('autoscale', True)
        self.worker_autoscale = self.kwargs.get('worker_autoscale', True)
        self.engine_version = self.kwargs.get('db_engine_version', '15.4')
        self.desired_web_count = self.kwargs.get('desired_web_count', 2)
        self.desired_worker_count = self.kwargs.get('desired_worker_count', 1)
        self.rds_minimum_capacity = self.kwargs.get('rds_minimum_capacity', 1)
        self.rds_maximum_capacity = self.kwargs.get('rds_maximum_capacity', 128)
        self.kwargs['sns_topic_arn'] = self.kwargs.get('sns_topic_arn',
                                                       operations.get_opsgenie_sns_topic_arn())

        self.env_name = os.environ.get('ENVIRONMENT_NAME', 'stage')

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
        
        ecs_client = kwargs.get('ecs_client') or boto3.client('ecs', region_name='us-west-2')

        possible_service_names = [
            self.namespace,  
            f"{self.namespace}-{self.namespace}-container", 
        ]

        found_service = False
        for service_name in possible_service_names:
            try:
                response = ecs_client.describe_services(
                    cluster=self.namespace,
                    services=[service_name]
                )

                if response.get('services') and len(response['services']) > 0:
                    self.current_desired_count = response['services'][0]['desiredCount']
                    pulumi.log.info(f"Found service {service_name} with desired count: {self.current_desired_count}")
                    found_service = True
                    break
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code in ['ClusterNotFoundException', 'ServiceNotFoundException']:
                    pulumi.log.info(f"Service {service_name} not found: {e}")
                    continue
                else:
                    pulumi.log.warn(f"Unexpected error checking service {service_name}: {str(e)}")
                    continue

        if not found_service:
            pulumi.log.info("No existing services found, using default desired count")
            self.current_desired_count = self.desired_web_count

        self.rds()

        self.setup_dynamo()

        self.setup_redis()

        self.secrets()

        self.ecs()

        self.security()

        self.register_outputs({})

        if self.env_name == "prod":
            self.setup_dashboard(self.namespace)

    def setup_redis(self):
        if sidekiq_present():
            self.env_vars['REDIS_PROVIDER'] = 'QUEUE_REDIS_URL'
            if 'queue_redis' not in self.kwargs:
                self.kwargs['queue_redis'] = True
        if 'queue_redis' in self.kwargs:
            queue_redis_kwargs = {}
            if 'namespace' in self.kwargs:
                queue_redis_kwargs['namespace'] = self.kwargs['namespace']

            if isinstance(self.kwargs['queue_redis'], RedisComponent):
                self.queue_redis = self.kwargs['queue_redis']
            elif self.kwargs['queue_redis']:
                self.queue_redis = QueueComponent(qualify_component_name('queue-redis', self.kwargs),
                                                  **queue_redis_kwargs)

            if self.queue_redis:
                self.env_vars['QUEUE_REDIS_URL'] = self.queue_redis.url
        if 'cache_redis' in self.kwargs:
            if isinstance(self.kwargs['cache_redis'], RedisComponent):
                self.cache_redis = self.kwargs['cache_redis']
            elif self.kwargs['cache_redis']:
                cache_redis_kwargs = {}
                if 'namespace' in self.kwargs:
                    cache_redis_kwargs['namespace'] = self.kwargs['namespace']
                self.cache_redis = CacheComponent(qualify_component_name('cache-redis', self.kwargs),
                                                  **cache_redis_kwargs)

            if self.cache_redis:
                self.env_vars['CACHE_REDIS_URL'] = self.cache_redis.url
                self.env_vars['REDIS_SERVER'] = self.cache_redis.url

    def security(self):
        self.firewall_rule = aws.ec2.SecurityGroupRule(
            qualify_component_name('rds_security_group_rule', self.kwargs),
            type='ingress',
            from_port=5432,
            to_port=5432,
            protocol='tcp',
            security_group_id=self.rds_serverless_cluster.vpc_security_group_ids[0],
            source_security_group_id=self.container_security_groups[0],
            opts=pulumi.ResourceOptions(parent=self,
                                        depends_on=[self.rds_serverless_cluster_instance,
                                                    self.web_container])
        )

    def ecs(self):
        self.ecs_cluster = create_ecs_cluster(self, self.namespace, self.kwargs)
        self.kwargs['ecs_cluster'] = self.ecs_cluster

        container_image = os.environ['CONTAINER_IMAGE']
        master_key = os.environ['RAILS_MASTER_KEY']
        additional_env_vars = {
            'RAILS_MASTER_KEY': master_key,
            'DATABASE_HOST': self.rds_serverless_cluster.endpoint,
            'DB_HOST': self.rds_serverless_cluster.endpoint,
            'DB_USERNAME': self.db_username,
            'DB_USER': self.db_username,
            'DB_PASSWORD': self.db_password.result,
            'DB_PASS': self.db_password.result,
            'DB_NAME': self.db_name,
            'DB_PORT': '5432',
            'DATABASE_URL': self.get_database_url(),
            'RAILS_ENV': 'production',
            'NAMESPACE': self.namespace
        }

        self.env_vars.update(additional_env_vars)
        self.kwargs['env_vars'] = self.env_vars
        self.kwargs['secrets'] = self.secret.get_secrets()  # pragma: no cover
        self.kwargs['container_image'] = container_image

        execution_entry_point = self.kwargs.get("execution_entry_point", [])
        self.kwargs['entry_point'] = execution_entry_point

        execution_cmd = self.kwargs.get("execution_cmd",
                                        ["sh", "-c",
                                         "bundle exec rails db:prepare db:migrate db:seed assets:precompile && "
                                         "echo 'Migrations complete'"])
        self.kwargs['command'] = execution_cmd

        if self.kwargs.get('storage', False):
            self.setup_storage()
            self.kwargs['env_vars'].update(self.storage.s3_env_vars)

        self.kwargs['autoscale'] = False
        self.kwargs['worker_autoscale'] = False

        self.migration_container = ContainerComponent(
            qualify_component_name("migration", self.kwargs),
            need_load_balancer=False,
            desired_count=0,
            opts=pulumi.ResourceOptions(parent=self,
                                        depends_on=[self.rds_serverless_cluster_instance]),
            **self.kwargs
        )

        subnets = self.kwargs.get(
            'container_subnets',
            self.migration_container.fargate_service.service.network_configuration.subnets)  # pragma: no cover
        self.container_security_groups = self.kwargs.get(
            'container_security_groups',
            self.migration_container.fargate_service.service.network_configuration.security_groups)  # pragma: no cover
        execution_inputs = ExecutionResourceInputs(
            cluster=self.ecs_cluster.arn,
            family=self.migration_container.namespace,
            subnets=subnets,
            security_groups=self.container_security_groups,
        )
        self.execution = ExecutionComponent(qualify_component_name("execution", self.kwargs),
                                            execution_inputs,
                                            opts=pulumi.ResourceOptions(parent=self,
                                                                        depends_on=[self.migration_container]))

        web_entry_point = self.kwargs.get('web_entry_point')
        web_command = self.kwargs.get('web_cmd', ["sh", "-c", "rails assets:precompile && rails server -b 0.0.0.0"])

        self.kwargs['secrets'] = self.secret.get_secrets()  # pragma: no cover
        self.kwargs['entry_point'] = web_entry_point
        self.kwargs['command'] = web_command
        self.kwargs['desired_count'] = self.current_desired_count
        self.kwargs['autoscale'] = self.autoscale
        self.kwargs['worker_autoscale'] = False
        
        self.web_container = ContainerComponent(qualify_component_name("container", self.kwargs),
                                                pulumi.ResourceOptions(parent=self,
                                                                       depends_on=[self.execution]
                                                                       ),
                                                **self.kwargs
                                                )
        self.need_worker = self.kwargs.get('need_worker', None)
        if self.need_worker is None:  # pragma: no cover
            # If we don't know if we need a worker, check for sidekiq in the Gemfile
            self.need_worker = sidekiq_present()

        if self.need_worker:
            self.setup_worker()

    def setup_worker(self):  # , execution):
        worker_cmd = self.kwargs.get('worker_cmd', ["sh", "-c", "bundle exec sidekiq"])
        worker_entry_point = self.kwargs.get('worker_entry_point')
        if "WORKER_CONTAINER_IMAGE" in os.environ:
            self.kwargs['container_image'] = os.environ["WORKER_CONTAINER_IMAGE"]
        self.kwargs['entry_point'] = worker_entry_point
        self.kwargs['command'] = worker_cmd
        if self.kwargs.get('worker_cpu'):
            self.kwargs['cpu'] = self.kwargs.get('worker_cpu')
        if self.kwargs.get('worker_memory'):
            self.kwargs['memory'] = self.kwargs.get('worker_memory')
        self.kwargs['ecs_cluster_arn'] = self.ecs_cluster.arn
        self.kwargs['need_load_balancer'] = False
        self.kwargs['secrets'] = self.secret.get_secrets()  # pragma: no cover
        self.kwargs['log_metric_filters'] = self.worker_log_metric_filters
        self.kwargs['desired_count'] = self.desired_worker_count
        self.kwargs['autoscale'] = False
        self.kwargs['worker_autoscale'] = self.worker_autoscale
        self.kwargs['deployment_maximum_percent'] = 200

        self.worker_container = ContainerComponent(qualify_component_name("worker", self.kwargs),
                                                   pulumi.ResourceOptions(parent=self,
                                                                          depends_on=[self.execution]
                                                                          ),
                                                   **self.kwargs
                                                   )
        self.kwargs['log_metric_filters'] = []

    def secrets(self):
        self.secret = SecretsComponent(qualify_component_name("secrets", self.kwargs),
                                       pulumi.ResourceOptions(parent=self),
                                       **self.kwargs
                                       )

    def salt_and_hash_password(self, pwd):
        string_to_hash = f'{pwd}{self.db_username}'
        hashed = hashlib.md5(string_to_hash.encode('utf-8')).hexdigest()
        return f'md5{hashed}'

    def rds(self):
        self.db_username = self.kwargs.get("db_username", self.namespace.replace('-', '_'))
        self.db_password = random.RandomPassword(qualify_component_name("password", self.kwargs),
                                                                 length=30,
                                                                 special=False,)
        self.db_name = self.kwargs.get("db_name", "app")

        self.hashed_password = self.db_password.result.apply(self.salt_and_hash_password)

        master_db_password = self.db_password.result
        if self.kwargs.get('md5_hash_db_password'):
            master_db_password = self.hashed_password

        self.rds_serverless_cluster = aws.rds.Cluster(
            qualify_component_name('rds_serverless_cluster', self.kwargs),
            cluster_identifier=self.namespace,
            engine='aurora-postgresql',
            engine_mode='provisioned',
            engine_version=self.engine_version,
            database_name=self.db_name,
            master_username=self.db_username,
            master_password=master_db_password,
            apply_immediately=True,
            deletion_protection=True,
            skip_final_snapshot=False,
            final_snapshot_identifier=f'{self.namespace}-final-snapshot',
            backup_retention_period=14,
            serverlessv2_scaling_configuration=aws.rds.ClusterServerlessv2ScalingConfigurationArgs(
                min_capacity=self.rds_minimum_capacity,
                max_capacity=self.rds_maximum_capacity,
            ),
            snapshot_identifier=self.snapshot_identifier,
            kms_key_id=self.kms_key_id,
            storage_encrypted=bool(self.kms_key_id),
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self,  # pragma: no cover
                                        protect=True,
                                        ignore_changes=[
                                                        'masterPassword', ## Don't change
                                                        'snapshotIdentifier', #* results in replace
                                                        'clusterIdentifier', #*
                                                        'engineVersion', ### results in an outage
                                                        'masterUsername', #*,
                                                        'storageEncrypted'
                                                        ])
        )
        self.rds_serverless_cluster_instance = aws.rds.ClusterInstance(
            qualify_component_name('rds_serverless_cluster_instance', self.kwargs),
            identifier=self.namespace,
            cluster_identifier=self.rds_serverless_cluster.cluster_identifier,
            instance_class='db.serverless',
            engine=self.rds_serverless_cluster.engine,
            engine_version=self.rds_serverless_cluster.engine_version,
            apply_immediately=True,
            publicly_accessible=True,
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self,
                                        depends_on=[self.rds_serverless_cluster],
                                        protect=True,
                                        ignore_changes=[
                                            'masterPassword', ##
                                            'snapshotIdentifier', #*
                                            'clusterIdentifier', #*
                                            'identifier', #*
                                        ]),
        )

        export("db_endpoint", Output.concat(self.rds_serverless_cluster.endpoint))

    def get_database_url(self):
        return Output.concat('postgres://',
                             self.db_username,
                             ':',
                             self.db_password.result,
                             '@',
                             self.rds_serverless_cluster.endpoint,
                             ':5432/',
                             self.db_name)

    def setup_dynamo(self):
        for table_component in self.dynamo_tables:
            env_var_name = table_component._name.upper() + '_DYNAMO_TABLE_NAME'
            self.env_vars[env_var_name] = table_component.table.name

    def setup_storage(self):
        self.storage = StorageComponent(qualify_component_name("storage", self.kwargs),
                                        pulumi.ResourceOptions(parent=self, protect=True),
                                        **self.kwargs
                                        )
        self.env_vars.update(self.storage.s3_env_vars)

    def setup_dashboard(self, namespace):
        self.dashboard = DashboardComponent(qualify_component_name("dashboard", self.kwargs),
            namespace=self.namespace,
            web_container=self.web_container,
            ecs_cluster=self.ecs_cluster,
            rds_serverless_cluster_instance=self.rds_serverless_cluster_instance,
                                            opts=pulumi.ResourceOptions(parent=self, depends_on=self.ecs_cluster),
        )
