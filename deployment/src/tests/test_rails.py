import json
import hashlib
import os

import boto3
import pulumi.runtime
import pytest
from botocore.stub import Stubber

from strongmind_deployment.container import ContainerComponent
from strongmind_deployment.dynamo import DynamoComponent
from strongmind_deployment.redis import QueueComponent, CacheComponent
from strongmind_deployment.storage import StorageComponent
from tests.shared import assert_outputs_equal, assert_output_equals
from tests.mocks import get_pulumi_mocks


def describe_a_pulumi_rails_app():
    @pytest.fixture
    def app_name(faker):
        return faker.word()

    @pytest.fixture
    def environment(faker):
        return faker.word()

    @pytest.fixture
    def stack(faker, app_name, environment):
        return f"{app_name}-{environment}"

    @pytest.fixture
    def master_db_password(faker):
        return faker.password(length=30)

    @pytest.fixture
    def pulumi_mocks(faker, master_db_password):
        return get_pulumi_mocks(faker, master_db_password)

    @pytest.fixture
    def container_port(faker):
        return faker.random_int()

    @pytest.fixture
    def container_entry_point():
        # We will use the entry point from Dockerfile by default
        return None

    @pytest.fixture
    def worker_container_memory(faker):
        return faker.random_int()

    @pytest.fixture
    def worker_container_cpu(faker):
        return faker.random_int()

    @pytest.fixture
    def worker_container_entry_point():
        return ["sh", "-c", "bundle exec sidekiq"]

    @pytest.fixture
    def cpu(faker):
        return faker.random_int()

    @pytest.fixture
    def memory(faker):
        return faker.random_int()

    @pytest.fixture
    def aws_account_id(faker):
        return faker.random_int()

    @pytest.fixture
    def ecs_security_group(faker):
        return faker.word()

    @pytest.fixture
    def load_balancer_arn(faker):
        return f"arn:aws:elasticloadbalancing:us-west-2:{faker.random_int()}:loadbalancer/app/{faker.word()}/{faker.random_int()}"

    @pytest.fixture
    def target_group_arn(faker):
        return f"arn:aws:elasticloadbalancing:us-west-2:{faker.random_int()}:targetgroup/{faker.word()}/{faker.random_int()}"

    @pytest.fixture
    def domain_validation_options(faker):
        class FakeValidationOption:
            def __init__(self, name, value, type):
                self.resource_record_name = name
                self.resource_record_value = value
                self.resource_record_type = type

            pass

        return [FakeValidationOption(faker.word(), faker.word(), faker.word())]

    @pytest.fixture
    def load_balancer_dns_name(faker):
        return f"{faker.word()}.{faker.word()}.{faker.word()}"

    @pytest.fixture
    def zone_id(faker):
        return faker.word()

    @pytest.fixture
    def container_image(faker):
        image = f"{faker.word()}/{faker.word()}:{faker.word()}"
        os.environ["CONTAINER_IMAGE"] = image
        return image

    @pytest.fixture
    def rails_master_key(faker):
        key = faker.password(length=64)
        os.environ["RAILS_MASTER_KEY"] = key
        return key

    @pytest.fixture
    def component_kwargs(
            container_port,
            cpu,
            memory,
            ecs_security_group,
            load_balancer_arn,
            target_group_arn,
            load_balancer_dns_name,
            domain_validation_options,
            zone_id,
            environment,
            container_image,
            rails_master_key,
            worker_container_entry_point,
            worker_container_cpu,
            worker_container_memory,
            stubbed_ecs_client
    ):
        kwargs = {
            "container_port": container_port,
            "cpu": cpu,
            "memory": memory,
            "worker_entry_point": worker_container_entry_point,
            "worker_cpu": worker_container_cpu,
            "worker_memory": worker_container_memory,
            "container_security_group_id": ecs_security_group,
            "load_balancer_arn": load_balancer_arn,
            "target_group_arn": target_group_arn,
            "load_balancer_dns_name": load_balancer_dns_name,
            "domain_validation_options": domain_validation_options,
            "zone_id": zone_id,
            "env_vars": {
                "ENVIRONMENT_NAME": environment
            },
            "ecs_client": stubbed_ecs_client,
        }

        return kwargs

    @pytest.fixture
    def sut(pulumi_set_mocks,
            component_kwargs):
        import strongmind_deployment.rails

        sut = strongmind_deployment.rails.RailsComponent("rails",
                                                         **component_kwargs
                                                         )
        return sut

    @pytest.fixture
    def stubbed_ecs_client():
        ecs_client = boto3.client('ecs')
        stubber = Stubber(ecs_client)
        stubber.add_response(
            'run_task',
            {"tasks": [{
                "taskArn": "arn",
            }]},
            {
                "taskDefinition": "family",
                "cluster": "test_ecs_cluster",
                "launchType": "FARGATE",
                "networkConfiguration": {
                    "awsvpcConfiguration": {
                        "subnets": ["subnets"],
                        "securityGroups": ["security_groups"],
                        "assignPublicIp": "ENABLED"
                    }
                },
                "startedBy": "rails-component"
            }
        )
        stubber.add_response('describe_tasks', {"tasks":
            [{
                "lastStatus": "STOPPED",
                "containers": [{
                    "exitCode": 0,
                }]
            }]
        }
                             )
        stubber.activate()
        yield ecs_client
        stubber.deactivate()

    @pulumi.runtime.test
    def it_exists(sut):
        assert sut

    @pulumi.runtime.test
    def it_has_no_dynamo_tables(sut):
        assert sut.dynamo_tables == []

    def describe_secretmanager_secret():
        @pulumi.runtime.test
        def it_has_a_secret(sut):
            assert sut.secret.sm_secret

        @pulumi.runtime.test
        def it_has_a_secret_version(sut):
            assert sut.secret.sm_secret_version

        @pulumi.runtime.test
        def it_has_a_sm_secret_version_secret_string(sut):
            return assert_output_equals(sut.secret.sm_secret_version.secret_string, "{}")

        def describe_with_secrets_provided():
            @pytest.fixture()
            def secret_key_1(faker):
                return faker.word()

            @pytest.fixture()
            def secret_value_1(faker):
                return faker.word()

            @pytest.fixture()
            def secret_key_2(faker):
                return faker.word()

            @pytest.fixture()
            def secret_value_2(faker):
                return faker.word()

            @pytest.fixture
            def secrets_string(secret_key_1, secret_value_1, secret_key_2, secret_value_2):
                return json.dumps({secret_key_1: secret_value_1, secret_key_2: secret_value_2})

            @pytest.fixture
            def pulumi_mocks(faker, master_db_password, secrets_string):
                return get_pulumi_mocks(faker, master_db_password, secrets_string)

            @pytest.fixture
            def component_kwargs(component_kwargs, secrets_string):
                component_kwargs['secrets_string'] = secrets_string
                return component_kwargs

            @pulumi.runtime.test
            def it_passes_secrets_to_web_container(sut):
                # Not sure how to best compare two coroutines, but this at least ensures they are named the same
                assert sut.web_container.secrets.__name__ == sut.secret.get_secrets().__name__

            @pytest.fixture
            def actual_secrets(sut):
                return sut.secret.get_known_secrets()

            @pulumi.runtime.test
            def it_formats_secrets_for_web_container(actual_secrets, secret_key_1, secret_key_2):
                assert actual_secrets == [
                    {
                        'name': secret_key_1,
                        'valueFrom': f'arn:aws:secretsmanager:us-west-2:123456789013:secret/my-secrets:{secret_key_1}::'
                    },
                    {
                        'name': secret_key_2,
                        'valueFrom': f'arn:aws:secretsmanager:us-west-2:123456789013:secret/my-secrets:{secret_key_2}::'
                    }
                ]

    def describe_a_rds_postgres_cluster():
        @pulumi.runtime.test
        def it_has_a_password(sut):
            assert sut.db_password

        @pulumi.runtime.test
        def it_has_an_md5_password_hashed_with_the_username_as_a_salt(sut):
            def check_password(args):
                pwd, hashed_pwd = args
                m = hashlib.md5()

                string_to_hash = f"{pwd}{sut.db_username}"
                m.update(string_to_hash.encode())
                assert hashed_pwd.startswith('md5')
                assert hashed_pwd == f"md5{m.hexdigest()}"

            return pulumi.Output.all(sut.db_password.result, sut.hashed_password).apply(check_password)

        @pulumi.runtime.test
        def it_has_a_password_with_30_chars(sut):
            def check_password(pwd):
                assert len(pwd) == 30

            return sut.db_password.result.apply(check_password)

        @pulumi.runtime.test
        def it_has_a_password_with_no_special_chars(sut):
            def check_special(special):
                assert special is False

            return sut.db_password.special.apply(check_special)

        @pulumi.runtime.test
        def it_creates_a_aurora_postgres_cluster(sut):
            def check_rds_cluster_engine(args):
                cluster_engine, engine_mode, engine_version = args
                assert cluster_engine == 'aurora-postgresql'
                assert engine_mode == 'provisioned'
                assert engine_version == '15.2'

            return pulumi.Output.all(
                sut.rds_serverless_cluster.engine,
                sut.rds_serverless_cluster.engine_mode,
                sut.rds_serverless_cluster.engine_version
            ).apply(check_rds_cluster_engine)

        @pulumi.runtime.test
        def it_sets_the_name_to_the_app_name(sut, stack, app_name):
            return assert_output_equals(sut.rds_serverless_cluster.cluster_identifier, f'{app_name}-{stack}')

        @pulumi.runtime.test
        def it_sets_the_master_username(sut, stack, app_name):
            return assert_output_equals(sut.rds_serverless_cluster.master_username,
                                        f'{app_name}-{stack}'.replace('-', '_'))

        @pulumi.runtime.test
        def it_sets_the_master_password(sut):
            return assert_outputs_equal(sut.rds_serverless_cluster.master_password, sut.db_password.result)

        @pulumi.runtime.test
        def it_turns_on_deletion_protection(sut):
            return assert_output_equals(sut.rds_serverless_cluster.deletion_protection, True)

        @pulumi.runtime.test
        def it_sets_skip_final_snapshot_to_false(sut):
            return assert_output_equals(sut.rds_serverless_cluster.skip_final_snapshot, False)

        @pulumi.runtime.test
        def it_sets_a_serverlessv2_scaling_configuration(sut):
            def check_rds_cluster_scaling_configuration(args):
                min_capacity, max_capacity = args
                assert min_capacity == 0.5
                assert max_capacity == 16

            return pulumi.Output.all(
                sut.rds_serverless_cluster.serverlessv2_scaling_configuration.min_capacity,
                sut.rds_serverless_cluster.serverlessv2_scaling_configuration.max_capacity,
            ).apply(check_rds_cluster_scaling_configuration)

        @pulumi.runtime.test
        def it_sends_the_cluster_url_to_the_ecs_environment(sut):
            def check_ecs_environment(args):
                postgres_url, endpoint, master_username, master_password = args
                expected_postgres_url = f'postgres://{master_username}:{master_password}@{endpoint}:5432/app'

                assert postgres_url == expected_postgres_url

            return pulumi.Output.all(
                sut.web_container.env_vars["DATABASE_URL"],
                sut.rds_serverless_cluster.endpoint,
                sut.rds_serverless_cluster.master_username,
                sut.db_password.result
            ).apply(check_ecs_environment)

        @pulumi.runtime.test
        def it_sets_the_rails_environment(sut):
            assert sut.web_container.env_vars["RAILS_ENV"] == "production"

        @pulumi.runtime.test
        def it_sends_the_cluster_endpoint_to_the_ecs_environment(sut):
            def check_ecs_environment(args):
                actual_host, expected_endpoint = args
                assert actual_host == expected_endpoint

            return pulumi.Output.all(
                sut.web_container.env_vars["DATABASE_HOST"],
                sut.rds_serverless_cluster.endpoint
            ).apply(check_ecs_environment)

        @pulumi.runtime.test
        def it_sends_the_cluster_username_to_the_ecs_environment(sut):
            def check_ecs_environment(args):
                actual_username, expected_username = args
                assert actual_username == expected_username

            return pulumi.Output.all(
                sut.web_container.env_vars["DB_USERNAME"],
                sut.rds_serverless_cluster.master_username
            ).apply(check_ecs_environment)

        @pulumi.runtime.test
        def it_sends_the_cluster_password_to_the_ecs_environment(sut):
            def check_ecs_environment(args):
                actual_password, expected_password = args
                assert actual_password == expected_password

            return pulumi.Output.all(
                sut.web_container.env_vars["DB_PASSWORD"],
                sut.db_password.result
            ).apply(check_ecs_environment)

        def describe_with_md5_passwords_on():
            @pytest.fixture
            def component_kwargs(component_kwargs):
                component_kwargs['md5_hash_db_password'] = True
                return component_kwargs

            @pulumi.runtime.test
            def it_sets_the_master_password(sut):
                return assert_outputs_equal(sut.rds_serverless_cluster.master_password, sut.hashed_password)

    def describe_a_rds_postgres_cluster_instance():
        @pulumi.runtime.test
        def it_creates_a_aurora_postgres_cluster_instance(sut, stack, app_name):
            def check_rds_cluster_instance_engine(args):
                cluster_identifier, instance_class = args
                assert cluster_identifier == f"{app_name}-{stack}"
                assert instance_class == 'db.serverless'

            return pulumi.Output.all(
                sut.rds_serverless_cluster_instance.cluster_identifier,
                sut.rds_serverless_cluster_instance.instance_class
            ).apply(check_rds_cluster_instance_engine)

        @pulumi.runtime.test
        def it_has_the_same_engine_as_the_cluster(sut):
            def check_rds_cluster_instance_engine(args):
                engine, cluster_engine = args
                assert engine == cluster_engine

            return pulumi.Output.all(
                sut.rds_serverless_cluster_instance.engine,
                sut.rds_serverless_cluster.engine
            ).apply(check_rds_cluster_instance_engine)

        @pulumi.runtime.test
        def it_has_the_same_engine_version_as_the_cluster(sut):
            def check_rds_cluster_instance_engine_version(args):
                engine_version, cluster_engine_version = args
                assert engine_version == cluster_engine_version

            return pulumi.Output.all(
                sut.rds_serverless_cluster_instance.engine_version,
                sut.rds_serverless_cluster.engine_version
            ).apply(check_rds_cluster_instance_engine_version)

        @pulumi.runtime.test
        def it_has_the_app_name(sut, stack, app_name):
            def check_rds_cluster_instance_identifier(args):
                identifier = args[0]
                assert identifier == f"{app_name}-{stack}"

            return pulumi.Output.all(
                sut.rds_serverless_cluster_instance.identifier,
            ).apply(check_rds_cluster_instance_identifier)

        @pulumi.runtime.test
        def it_is_publicly_accessible(sut, app_name):
            return assert_output_equals(sut.rds_serverless_cluster_instance.publicly_accessible, True)

    def describe_a_ecs_task():
        @pulumi.runtime.test
        def it_creates_a_web_container_component(sut,
                                                 container_port,
                                                 cpu,
                                                 memory):
            def check_machine_specs(args):
                port, container_cpu, container_memory = args
                assert port == container_port
                assert container_cpu == cpu
                assert container_memory == memory

            return pulumi.Output.all(
                sut.web_container.container_port,
                sut.web_container.cpu,
                sut.web_container.memory
            ).apply(check_machine_specs)

        @pulumi.runtime.test
        def it_uses_rails_entry_point(sut, container_entry_point):
            assert sut.web_container.entry_point == container_entry_point

        def describe_with_need_worker_set():
            @pytest.fixture
            def component_kwargs(component_kwargs):
                component_kwargs['need_worker'] = True
                return component_kwargs

            @pulumi.runtime.test
            def it_creates_a_worker_container_component(sut,
                                                        worker_container_cpu,
                                                        worker_container_memory):
                def check_machine_specs(args):
                    container_cpu, container_memory = args
                    assert container_cpu == worker_container_cpu
                    assert container_memory == worker_container_memory

                return pulumi.Output.all(
                    sut.worker_container.cpu,
                    sut.worker_container.memory
                ).apply(check_machine_specs)

            @pulumi.runtime.test
            def it_uses_sidekiq_entry_point_for_worker(sut, worker_container_entry_point):
                assert sut.worker_container.entry_point == worker_container_entry_point

            @pulumi.runtime.test
            def it_does_not_need_load_balancer(sut):
                assert not sut.worker_container.need_load_balancer

            @pulumi.runtime.test
            def it_uses_cluster_from_web_container(sut):
                assert sut.worker_container.ecs_cluster_arn == sut.web_container.ecs_cluster_arn

    @pulumi.runtime.test
    def it_allows_container_to_talk_to_rds(sut, ecs_security_group):
        assert sut.firewall_rule
        return assert_outputs_equal(sut.firewall_rule.security_group_id,
                                    sut.rds_serverless_cluster.vpc_security_group_ids[0]) \
            and assert_output_equals(sut.firewall_rule.source_security_group_id, ecs_security_group)

    @pulumi.runtime.test
    def it_does_not_create_a_queue_redis(sut):
        # to save money, we don't create a queue redis if it is not requested
        assert sut.queue_redis is None

    @pulumi.runtime.test
    def it_does_not_create_a_cache_redis(sut):
        # to save money, we don't create a cache redis if it is not requested
        assert sut.cache_redis is None

    @pulumi.runtime.test
    def it_does_not_create_a_worker_container(sut):
        assert sut.worker_container is None

    def describe_with_sidekiq_present():
        @pytest.fixture
        def sidekiq_present(when):
            from strongmind_deployment import rails
            when(rails).sidekiq_present().thenReturn(True)

        @pytest.fixture
        def sut(sidekiq_present, sut):
            return sut

        @pulumi.runtime.test
        def it_creates_a_queue_redis(sut):
            assert hasattr(sut, 'queue_redis')

        @pulumi.runtime.test
        def it_configures_redis_provider(sut):
            assert sut.env_vars["REDIS_PROVIDER"] == "QUEUE_REDIS_URL"

        @pulumi.runtime.test
        def it_creates_a_worker_container(sut):
            assert isinstance(sut.worker_container, ContainerComponent)

        @pulumi.runtime.test
        def it_has_same_container_image(sut):
            return assert_outputs_equal(sut.worker_container.container_image, sut.web_container.container_image)

        def describe_with_different_worker_container():
            @pytest.fixture
            def container_image(faker):
                name = faker.word()
                os.environ["WORKER_CONTAINER_IMAGE"] = name
                return name

            @pulumi.runtime.test
            def it_has_different_container_image(sut, container_image):
                return assert_outputs_equal(sut.worker_container.container_image, container_image)

    def describe_with_queue_redis_enabled():
        @pytest.fixture
        def component_kwargs(component_kwargs):
            component_kwargs['queue_redis'] = True

            return component_kwargs

        @pulumi.runtime.test
        def it_creates_a_queue_redis(sut):
            assert isinstance(sut.queue_redis, QueueComponent)

        @pulumi.runtime.test
        def test_it_names_the_queue_redis(sut, app_name, stack):
            return assert_output_equals(sut.queue_redis.cluster.cluster_id, f"{app_name}-{stack}-queue-redis")

        @pulumi.runtime.test
        def it_sends_the_url_to_the_ecs_environment(sut):
            return assert_outputs_equal(sut.env_vars["QUEUE_REDIS_URL"], sut.queue_redis.url)

    def describe_with_custom_queue_redis():
        @pytest.fixture
        def component_kwargs(component_kwargs):
            component_kwargs['queue_redis'] = QueueComponent('custom-queue-redis')

            return component_kwargs

        @pulumi.runtime.test
        def it_creates_a_queue_redis(sut):
            assert isinstance(sut.queue_redis, QueueComponent)

        @pulumi.runtime.test
        def test_it_names_the_queue_redis(sut, app_name, stack):
            return assert_output_equals(sut.queue_redis.cluster.cluster_id, f"{app_name}-{stack}-custom-queue-redis")

    def describe_with_cache_redis_enabled():
        @pytest.fixture
        def component_kwargs(component_kwargs):
            component_kwargs['cache_redis'] = True

            return component_kwargs

        @pulumi.runtime.test
        def it_creates_a_cache_redis(sut):
            assert isinstance(sut.cache_redis, CacheComponent)

        @pulumi.runtime.test
        def it_names_the_cache_redis(sut, app_name, stack):
            return assert_output_equals(sut.cache_redis.cluster.cluster_id, f"{app_name}-{stack}-cache-redis")

        @pulumi.runtime.test
        def it_sends_the_url_to_the_ecs_environment(sut):
            return assert_outputs_equal(sut.env_vars["CACHE_REDIS_URL"], sut.cache_redis.url)

    def describe_with_custom_cache_redis():
        @pytest.fixture
        def component_kwargs(component_kwargs):
            component_kwargs['cache_redis'] = CacheComponent('custom-cache-redis')

            return component_kwargs

        @pulumi.runtime.test
        def it_creates_a_cache_redis(sut):
            assert isinstance(sut.cache_redis, CacheComponent)

        @pulumi.runtime.test
        def it_names_the_cache_redis(sut, app_name, stack):
            return assert_output_equals(sut.cache_redis.cluster.cluster_id, f"{app_name}-{stack}-custom-cache-redis")

    def describe_with_dynamo_tables():
        @pytest.fixture
        def dynamo_table_names(faker):
            return [faker.word(), faker.word()]

        @pytest.fixture
        def dynamo_tables(dynamo_table_names):
            tables = []
            for table_name in dynamo_table_names:
                tables.append(DynamoComponent(table_name, hash_key='id'))

            return tables

        @pytest.fixture
        def sut(component_kwargs, dynamo_tables, pulumi_set_mocks, stubbed_ecs_client):
            import strongmind_deployment.rails
            component_kwargs['dynamo_tables'] = dynamo_tables
            component_kwargs['ecs_client'] = stubbed_ecs_client

            return strongmind_deployment.rails.RailsComponent("rails",
                                                              **component_kwargs
                                                              )

        @pulumi.runtime.test
        def it_creates_dynamo_tables(sut, dynamo_tables):
            assert sut.dynamo_tables == dynamo_tables

        @pulumi.runtime.test
        def it_adds_the_first_table_name_to_the_env_vars(sut, dynamo_table_names, dynamo_tables):
            env_name = dynamo_table_names[0].upper() + "_DYNAMO_TABLE_NAME"
            return assert_outputs_equal(sut.env_vars[env_name], dynamo_tables[0].table.name)

        @pulumi.runtime.test
        def it_adds_the_second_table_name_to_the_env_vars(sut, dynamo_table_names, dynamo_tables):
            env_name = dynamo_table_names[1].upper() + "_DYNAMO_TABLE_NAME"
            return assert_outputs_equal(sut.env_vars[env_name], dynamo_tables[1].table.name)

    def describe_with_storage_enabled():
        @pytest.fixture
        def component_kwargs(component_kwargs):
            component_kwargs['storage'] = True

            return component_kwargs

        @pulumi.runtime.test
        def it_creates_a_storage_bucket(sut):
            assert isinstance(sut.storage, StorageComponent)

        @pulumi.runtime.test
        def it_sends_the_bucket_name_to_the_ecs_environment(sut):
            return assert_outputs_equal(sut.env_vars["S3_BUCKET_NAME"], sut.storage.bucket.bucket)
