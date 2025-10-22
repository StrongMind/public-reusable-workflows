import os
import subprocess
import hashlib

import pulumi
import pulumi_aws as aws
import pulumi_random as random
from pulumi import Output, export

from strongmind_deployment.util import qualify_component_name


class DatabaseComponent(pulumi.ComponentResource):
    def __init__(self, name, opts=None, **kwargs):
        """
        Resource that creates an Aurora PostgreSQL Serverless v2 database cluster with RDS Proxy.

        :param name: The _unique_ name of the resource.
        :param opts: A bag of optional settings that control this resource's behavior.
        :key namespace: A name to override the default naming of resources.
        :key db_name: The name of the database. Defaults to 'app'.
        :key db_username: The username for connecting to the database. Defaults to namespace with hyphens replaced by underscores.
        :key db_engine_version: The version of the database engine. Defaults to '15.4'.
        :key rds_minimum_capacity: The minimum capacity of the RDS cluster. Defaults to 1.
        :key rds_maximum_capacity: The maximum capacity of the RDS cluster. Defaults to 128.
        :key snapshot_identifier: The snapshot identifier to use for the RDS cluster. Defaults to None.
        :key kms_key_id: The KMS key ID to use for the RDS cluster. Defaults to None.
        :key md5_hash_db_password: Whether to MD5 hash the database password. Defaults to False.
        :key writer_instance_count: Number of writer instances. Defaults to 1.
        :key reader_instance_count: Number of reader instances. Defaults to 2.
        :key vpc_subnet_ids: List of VPC subnet IDs for the RDS Proxy. Optional.
        :key vpc_security_group_ids: List of VPC security group IDs for the RDS Proxy. Optional.
        """
        super().__init__('strongmind:global_build:commons:database', name, None, opts)
        
        self.kwargs = kwargs
        self.env_name = os.environ.get('ENVIRONMENT_NAME', 'stage')
        self.vpc_subnet_ids = self.kwargs.get('vpc_subnet_ids', None)
        self.vpc_security_group_ids = self.kwargs.get('vpc_security_group_ids', None)
        
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

        # Database configuration
        self.db_name = self.kwargs.get("db_name", "app")
        self.db_username = self.kwargs.get("db_username", self.namespace.replace('-', '_'))
        self.engine_version = self.kwargs.get('db_engine_version', '15.4')
        self.rds_minimum_capacity = self.kwargs.get('rds_minimum_capacity', 1)
        self.rds_maximum_capacity = self.kwargs.get('rds_maximum_capacity', 128)
        self.snapshot_identifier = self.kwargs.get('snapshot_identifier', None)
        self.kms_key_id = self.kwargs.get('kms_key_id', None)
        self.writer_instance_count = self.kwargs.get('writer_instance_count', 1)
        self.reader_instance_count = self.kwargs.get('reader_instance_count', 2)
        
        # Generate password
        self.db_password = random.RandomPassword(
            qualify_component_name("password", self.kwargs),
            length=30,
            special=False,
            opts=pulumi.ResourceOptions(parent=self)
        )
        
        self.hashed_password = self.db_password.result.apply(self.salt_and_hash_password)
        
        master_db_password = self.db_password.result
        if self.kwargs.get('md5_hash_db_password'):
            master_db_password = self.hashed_password
        
        # Create RDS Cluster
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
            opts=pulumi.ResourceOptions(
                parent=self,
                protect=True,
                ignore_changes=[
                    'masterPassword',  # Don't change
                    'snapshotIdentifier',  # results in replace
                    'clusterIdentifier',
                    'engineVersion',  # results in an outage
                    'masterUsername',
                    'storageEncrypted'
                ]
            )
        )
        
        # Create cluster instances (writers and readers)
        self.cluster_instances = []
        
        # Create writer instances
        for i in range(self.writer_instance_count):
            instance_identifier = f"{self.namespace}-writer-{i}" if i > 0 else self.namespace
            writer_instance = aws.rds.ClusterInstance(
                qualify_component_name(f'rds_writer_instance_{i}', self.kwargs),
                identifier=instance_identifier,
                cluster_identifier=self.rds_serverless_cluster.cluster_identifier,
                instance_class='db.serverless',
                engine=self.rds_serverless_cluster.engine,
                engine_version=self.rds_serverless_cluster.engine_version,
                apply_immediately=True,
                publicly_accessible=True,
                promotion_tier=i,  # Lower tier = higher priority for promotion
                tags=self.tags,
                opts=pulumi.ResourceOptions(
                    parent=self,
                    depends_on=[self.rds_serverless_cluster],
                    protect=True,
                    ignore_changes=[
                        'masterPassword',
                        'snapshotIdentifier',
                        'clusterIdentifier',
                        'identifier',
                    ]
                ),
            )
            self.cluster_instances.append(writer_instance)
        
        # Create reader instances
        for i in range(self.reader_instance_count):
            reader_instance = aws.rds.ClusterInstance(
                qualify_component_name(f'rds_reader_instance_{i}', self.kwargs),
                identifier=f"{self.namespace}-reader-{i}",
                cluster_identifier=self.rds_serverless_cluster.cluster_identifier,
                instance_class='db.serverless',
                engine=self.rds_serverless_cluster.engine,
                engine_version=self.rds_serverless_cluster.engine_version,
                apply_immediately=True,
                publicly_accessible=True,
                promotion_tier=self.writer_instance_count + i + 1,  # Higher tier = lower priority
                tags=self.tags,
                opts=pulumi.ResourceOptions(
                    parent=self,
                    depends_on=[self.rds_serverless_cluster],
                    protect=True,
                    ignore_changes=[
                        'masterPassword',
                        'snapshotIdentifier',
                        'clusterIdentifier',
                        'identifier',
                    ]
                ),
            )
            self.cluster_instances.append(reader_instance)
        
        # For backward compatibility, keep the first instance as rds_serverless_cluster_instance
        self.rds_serverless_cluster_instance = self.cluster_instances[0]
        
        # Create RDS Proxy
        self.create_rds_proxy()
        
        export("db_endpoint", Output.concat(self.rds_serverless_cluster.endpoint))
        if self.rds_proxy:
            export("db_proxy_endpoint", Output.concat(self.rds_proxy.endpoint))
        
        self.register_outputs({})
    
    def salt_and_hash_password(self, pwd):
        """Hash the password with username salt for MD5 authentication."""
        string_to_hash = f'{pwd}{self.db_username}'
        hashed = hashlib.md5(string_to_hash.encode('utf-8')).hexdigest()
        return f'md5{hashed}'
    
    def create_rds_proxy(self):
        """Create an RDS Proxy for connection pooling."""
        # Only create RDS Proxy if VPC subnet IDs are provided
        if self.vpc_subnet_ids:
            # Create a secret for the proxy to use
            self.proxy_secret = aws.secretsmanager.Secret(
                qualify_component_name('rds_proxy_secret', self.kwargs),
                name=f"{self.namespace}-rds-proxy-secret",
                tags=self.tags,
                opts=pulumi.ResourceOptions(parent=self)
            )
            
            # Store the database credentials in the secret
            self.proxy_secret_version = aws.secretsmanager.SecretVersion(
                qualify_component_name('rds_proxy_secret_version', self.kwargs),
                secret_id=self.proxy_secret.id,
                secret_string=Output.all(
                    self.db_username,
                    self.db_password.result
                ).apply(lambda args: f'{{"username":"{args[0]}","password":"{args[1]}"}}'),
                opts=pulumi.ResourceOptions(parent=self.proxy_secret)
            )
            
            # Create IAM role for RDS Proxy
            assume_role_policy = aws.iam.get_policy_document(
                statements=[aws.iam.GetPolicyDocumentStatementArgs(
                    actions=["sts:AssumeRole"],
                    principals=[aws.iam.GetPolicyDocumentStatementPrincipalArgs(
                        type="Service",
                        identifiers=["rds.amazonaws.com"],
                    )],
                )]
            )
            
            self.proxy_role = aws.iam.Role(
                qualify_component_name('rds_proxy_role', self.kwargs),
                name=f"{self.namespace}-rds-proxy-role",
                assume_role_policy=assume_role_policy.json,
                tags=self.tags,
                opts=pulumi.ResourceOptions(parent=self)
            )
            
            # Create policy for the proxy role to access secrets
            self.proxy_policy = aws.iam.RolePolicy(
                qualify_component_name('rds_proxy_policy', self.kwargs),
                role=self.proxy_role.id,
                policy=self.proxy_secret.arn.apply(
                    lambda arn: f'''{{
                        "Version": "2012-10-17",
                        "Statement": [
                            {{
                                "Effect": "Allow",
                                "Action": [
                                    "secretsmanager:GetSecretValue"
                                ],
                                "Resource": "{arn}"
                            }}
                        ]
                    }}'''
                ),
                opts=pulumi.ResourceOptions(parent=self.proxy_role)
            )
            
            # Create the RDS Proxy
            proxy_args = {
                'name': f"{self.namespace}-rds-proxy",
                'engine_family': "POSTGRESQL",
                'auths': [aws.rds.ProxyAuthArgs(
                    auth_scheme="SECRETS",
                    iam_auth="DISABLED",
                    secret_arn=self.proxy_secret.arn,
                )],
                'role_arn': self.proxy_role.arn,
                'vpc_subnet_ids': self.vpc_subnet_ids,
                'require_tls': False,
                'tags': self.tags,
            }
            
            # Add security groups if provided
            if self.vpc_security_group_ids:
                proxy_args['vpc_security_group_ids'] = self.vpc_security_group_ids
            
            self.rds_proxy = aws.rds.Proxy(
                qualify_component_name('rds_proxy', self.kwargs),
                **proxy_args,
                opts=pulumi.ResourceOptions(
                    parent=self,
                    depends_on=[self.proxy_secret_version, self.proxy_policy] + self.cluster_instances
                )
            )
        
            # Create proxy target group
            self.proxy_default_target_group = aws.rds.ProxyDefaultTargetGroup(
                qualify_component_name('rds_proxy_target_group', self.kwargs),
                db_proxy_name=self.rds_proxy.name,
                connection_pool_config=aws.rds.ProxyDefaultTargetGroupConnectionPoolConfigArgs(
                    max_connections_percent=100,
                    max_idle_connections_percent=50,
                    connection_borrow_timeout=120,
                ),
                opts=pulumi.ResourceOptions(parent=self.rds_proxy)
            )
            
            # Attach the cluster to the proxy
            self.proxy_target = aws.rds.ProxyTarget(
                qualify_component_name('rds_proxy_target', self.kwargs),
                db_proxy_name=self.rds_proxy.name,
                target_group_name=self.proxy_default_target_group.name,
                db_cluster_identifier=self.rds_serverless_cluster.cluster_identifier,
                opts=pulumi.ResourceOptions(parent=self.proxy_default_target_group)
            )
        else:
            # If no VPC subnet IDs provided, set all proxy-related attributes to None
            self.proxy_secret = None
            self.proxy_secret_version = None
            self.proxy_role = None
            self.proxy_policy = None
            self.rds_proxy = None
            self.proxy_default_target_group = None
            self.proxy_target = None
    
    def get_database_url(self, use_proxy=False):
        """
        Get the database URL for connecting to the database.
        
        :param use_proxy: If True, returns the proxy endpoint URL. Otherwise returns the cluster endpoint URL.
        """
        endpoint = self.rds_proxy.endpoint if use_proxy else self.rds_serverless_cluster.endpoint
        return Output.concat(
            'postgres://',
            self.db_username,
            ':',
            self.db_password.result,
            '@',
            endpoint,
            ':5432/',
            self.db_name
        )
    
    @property
    def endpoint(self):
        """Returns the cluster endpoint."""
        return self.rds_serverless_cluster.endpoint
    
    @property
    def proxy_endpoint(self):
        """Returns the RDS Proxy endpoint if proxy is created, otherwise None."""
        return self.rds_proxy.endpoint if self.rds_proxy else None
    
    @property
    def reader_endpoint(self):
        """Returns the cluster reader endpoint."""
        return self.rds_serverless_cluster.reader_endpoint

