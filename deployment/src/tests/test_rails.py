import json
import hashlib
import os

import boto3
import pulumi.runtime
import pytest
from botocore.stub import Stubber
from pytest_describe import behaves_like

from strongmind_deployment.container import ContainerComponent
from strongmind_deployment.dynamo import DynamoComponent
from strongmind_deployment.redis import QueueComponent, CacheComponent
from strongmind_deployment.storage import StorageComponent
from tests.shared import assert_outputs_equal, assert_output_equals
from tests.mocks import get_pulumi_mocks


def a_pulumi_rails_app():
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
    def container_cmd():
        return ["sh", "-c", "rails assets:precompile && rails server -b 0.0.0.0"]

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
    def execution_container_cmd():
        return ["sh", "-c",
                "bundle exec rails db:prepare db:migrate db:seed assets:precompile && "
                "echo 'Migrations complete'"]

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
    def ecs_security_groups(faker):
        return [faker.word(), faker.word()]

    @pytest.fixture
    def ecs_subnets(faker):
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
            ecs_security_groups,
            ecs_subnets,
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
            "container_security_groups": ecs_security_groups,
            "container_subnets": ecs_subnets,
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
    def namespace(app_name, stack):
        return f"{app_name}-{stack}"

    @pytest.fixture
    def default_desired_count():
        return 2

    @pytest.fixture
    def stubbed_ecs_client(namespace, default_desired_count):
        ecs_client = boto3.client('ecs')
        stubber = Stubber(ecs_client)

        # First attempt - standard case (will fail)
        stubber.add_client_error(
            'describe_services',
            service_error_code='ServiceNotFoundException',
            expected_params={
                'cluster': namespace,
                'services': [namespace]
            }
        )

        # Second attempt - edge case (will succeed)
        stubber.add_response(
            'describe_services',
            {
                'services': [{
                    'desiredCount': default_desired_count,
                }]
            },
            {
                'cluster': namespace,
                'services': [f"{namespace}-{namespace}-container"]
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

    @pulumi.runtime.test
    def it_asks_the_web_container_to_automatically_scale(sut):
        assert sut.web_container.autoscaling

    def describe_with_no_memory_or_cpu_passed_to_kwargs():
        @pytest.fixture
        def component_kwargs(component_kwargs):
            component_kwargs.pop('memory')
            component_kwargs.pop('cpu')
            component_kwargs.pop('worker_memory')
            component_kwargs.pop('worker_cpu')
            component_kwargs['need_worker'] = True
            return component_kwargs

        @pulumi.runtime.test
        def it_defaults_cpu_and_memory_for_the_web(sut):
            def check_task_definition(args):
                task_definition_dict = args[0]
                container = task_definition_dict["container"]
                assert container["memory"] == 4096
                assert container["cpu"] == 2048

            return pulumi.Output.all(sut.web_container.fargate_service.task_definition_args).apply(check_task_definition)

        @pulumi.runtime.test
        def it_defaults_cpu_and_memory_for_the_worker(sut):
            def check_task_definition(args):
                task_definition_dict = args[0]
                container = task_definition_dict["container"]
                assert container["memory"] == 4096
                assert container["cpu"] == 2048

            return pulumi.Output.all(sut.worker_container.fargate_service.task_definition_args).apply(check_task_definition)

    def describe_when_desired_web_count_is_provided():
        @pytest.fixture
        def desired_web_count(faker):
            return faker.random_int()

        @pytest.fixture
        def default_desired_count(desired_web_count):
            return desired_web_count

        @pytest.fixture
        def component_kwargs(component_kwargs, desired_web_count):
            component_kwargs['desired_web_count'] = desired_web_count
            return component_kwargs

        @pulumi.runtime.test
        def it_sets_the_desired_web_count(sut):
            def check_desired_count(args):
                desired_count = args[0]
                assert sut.current_desired_count == desired_count
                return True
            return pulumi.Output.all(sut.web_container.fargate_service.desired_count).apply(check_desired_count)



@behaves_like(a_pulumi_rails_app)
def describe_a_pulumi_rails_component():
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
                assert engine_version == '15.4'

            return pulumi.Output.all(
                sut.rds_serverless_cluster.engine,
                sut.rds_serverless_cluster.engine_mode,
                sut.rds_serverless_cluster.engine_version
            ).apply(check_rds_cluster_engine)

        @pulumi.runtime.test
        def it_sets_the_name_to_the_app_name(sut, stack, app_name):
            return assert_output_equals(sut.rds_serverless_cluster.cluster_identifier, f'{app_name}-{stack}')

        def describe_with_a_custom_namespace():
            @pytest.fixture
            def namespace(faker):
                return f'{faker.word()}-{faker.word()}'

            @pytest.fixture
            def component_kwargs(component_kwargs, namespace):
                component_kwargs['namespace'] = namespace
                return component_kwargs

            @pulumi.runtime.test
            def it_creates_a_cluster_with_an_overridden_name(sut, namespace):
                return assert_output_equals(sut.rds_serverless_cluster.cluster_identifier, namespace)

            @pulumi.runtime.test
            def it_sets_final_snapshot_identifier(sut, namespace):
                return assert_output_equals(sut.rds_serverless_cluster.final_snapshot_identifier,
                                            f"{namespace}-final-snapshot")

            @pulumi.runtime.test
            def it_sets_the_master_username(sut, namespace):
                return assert_output_equals(sut.rds_serverless_cluster.master_username,
                                            f'{namespace}'.replace('-', '_'))

        @pulumi.runtime.test
        def it_sets_the_master_username(sut, stack, app_name):
            return assert_output_equals(sut.rds_serverless_cluster.master_username,
                                        f'{app_name}-{stack}'.replace('-', '_'))

        @pulumi.runtime.test
        def it_sets_apply_immediately(sut):
            return assert_output_equals(sut.rds_serverless_cluster.apply_immediately, True)

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
        def it_sets_final_snapshot_identifier(sut, app_name, stack):
            return assert_output_equals(sut.rds_serverless_cluster.final_snapshot_identifier,
                                        f"{app_name}-{stack}-final-snapshot")

        @pulumi.runtime.test
        def it_sets_the_backup_retention_period_to_14_days(sut):
            return assert_output_equals(sut.rds_serverless_cluster.backup_retention_period, 14)

        @pulumi.runtime.test
        def it_enables_cloudwatch_logs_exports_by_default(sut):
            def check_cloudwatch_logs(logs):
                assert logs == ["postgresql"]
            
            return sut.rds_serverless_cluster.enabled_cloudwatch_logs_exports.apply(check_cloudwatch_logs)

        def describe_with_cloudwatch_logs_disabled():
            @pytest.fixture
            def component_kwargs(component_kwargs):
                component_kwargs['enable_db_cloudwatch_logs'] = False
                return component_kwargs

            @pulumi.runtime.test
            def it_disables_cloudwatch_logs_exports(sut):
                def check_cloudwatch_logs(logs):
                    assert logs == []
                
                return sut.rds_serverless_cluster.enabled_cloudwatch_logs_exports.apply(check_cloudwatch_logs)

        def describe_with_cloudwatch_logs_explicitly_enabled():
            @pytest.fixture
            def component_kwargs(component_kwargs):
                component_kwargs['enable_db_cloudwatch_logs'] = True
                return component_kwargs

            @pulumi.runtime.test
            def it_enables_cloudwatch_logs_exports(sut):
                def check_cloudwatch_logs(logs):
                    assert logs == ["postgresql"]
                
                return sut.rds_serverless_cluster.enabled_cloudwatch_logs_exports.apply(check_cloudwatch_logs)

        @pulumi.runtime.test
        def it_sets_a_serverlessv2_scaling_configuration(sut):
            def check_rds_cluster_scaling_configuration(args):
                min_capacity, max_capacity = args
                assert min_capacity == 1
                assert max_capacity == 128

            return pulumi.Output.all(
                sut.rds_serverless_cluster.serverlessv2_scaling_configuration.min_capacity,
                sut.rds_serverless_cluster.serverlessv2_scaling_configuration.max_capacity,
            ).apply(check_rds_cluster_scaling_configuration)

        @pulumi.runtime.test
        def it_sets_the_rails_environment(sut):
            assert sut.web_container.env_vars["RAILS_ENV"] == "production"

        @pulumi.runtime.test
        def it_sends_the_cluster_endpoint_to_the_ecs_environment(sut):
            def check_ecs_environment(args):
                actual_host, actual_db_host, expected_endpoint = args
                assert actual_host == actual_db_host == expected_endpoint

            return pulumi.Output.all(
                sut.web_container.env_vars["DATABASE_HOST"],
                sut.web_container.env_vars["DB_HOST"],
                sut.rds_serverless_cluster.endpoint
            ).apply(check_ecs_environment)

        @pulumi.runtime.test
        def it_sends_the_db_port_to_the_ecs_environment(sut):
            assert sut.web_container.env_vars["DB_PORT"] == "5432"

        @pulumi.runtime.test
        def it_sets_process_type_env_var_for_web_container(sut):
            assert sut.web_container.env_vars["PROCESS_TYPE"] == "web"

        @pulumi.runtime.test
        def it_sends_the_cluster_username_to_the_ecs_environment(sut):
            def check_ecs_environment(args):
                actual_username, actual_user, expected_username = args
                assert actual_username == actual_user == expected_username

            return pulumi.Output.all(
                sut.web_container.env_vars["DB_USERNAME"],
                sut.web_container.env_vars["DB_USER"],
                sut.rds_serverless_cluster.master_username
            ).apply(check_ecs_environment)

        @pulumi.runtime.test
        def it_sends_the_cluster_password_to_the_ecs_environment(sut):
            def check_ecs_environment(args):
                actual_password, actual_pass, expected_password = args
                assert actual_password == actual_pass == expected_password

            return pulumi.Output.all(
                sut.web_container.env_vars["DB_PASSWORD"],
                sut.web_container.env_vars["DB_PASS"],
                sut.db_password.result
            ).apply(check_ecs_environment)

        @pulumi.runtime.test
        def it_has_a_default_db_name(sut):
            return sut.db_name == "app"

        def describe_with_md5_passwords_on():
            @pytest.fixture
            def component_kwargs(component_kwargs):
                component_kwargs['md5_hash_db_password'] = True
                return component_kwargs

            @pulumi.runtime.test
            def it_sets_the_master_password(sut):
                return assert_outputs_equal(sut.rds_serverless_cluster.master_password, sut.hashed_password)

        def describe_when_given_engine_version():
            @pytest.fixture
            def engine_version(faker):
                return faker.word()

            @pytest.fixture
            def component_kwargs(component_kwargs, engine_version):
                component_kwargs['db_engine_version'] = \
                    engine_version
                return component_kwargs

            @pulumi.runtime.test
            def it_sets_the_engine_version(sut, engine_version):
                return assert_output_equals(sut.rds_serverless_cluster.engine_version,
                                            engine_version)

        def describe_when_given_a_snapshot_to_restore_from():
            @pytest.fixture
            def snapshot_identifier(faker):
                return f'arn:aws:rds:us-west-2:448312246740:cluster-snapshot:{faker.word()}'

            @pytest.fixture
            def component_kwargs(component_kwargs, snapshot_identifier):
                component_kwargs['snapshot_identifier'] = \
                    snapshot_identifier
                return component_kwargs

            @pulumi.runtime.test
            def it_restores_the_snapshot(sut, snapshot_identifier):
                return assert_output_equals(sut.rds_serverless_cluster.snapshot_identifier,
                                            snapshot_identifier)

            def describe_with_optional_database_options():
                @pytest.fixture
                def db_name(faker):
                    return faker.word()

                @pytest.fixture
                def db_username(faker):
                    return faker.word()

                @pytest.fixture
                def component_kwargs(component_kwargs, db_name, db_username):
                    component_kwargs['db_name'] = db_name
                    component_kwargs['db_username'] = db_username
                    return component_kwargs

                @pulumi.runtime.test
                def it_should_set_the_db_name(sut, db_name):
                    return assert_output_equals(sut.rds_serverless_cluster.database_name, db_name)

                @pulumi.runtime.test
                def it_should_set_the_db_username(sut, db_username):
                    return assert_output_equals(sut.rds_serverless_cluster.master_username, db_username)

        def describe_with_reader_instances():
            @pytest.fixture
            def reader_count():
                return 2

            @pytest.fixture
            def component_kwargs(component_kwargs, reader_count):
                component_kwargs['reader_instance_count'] = reader_count
                return component_kwargs

            @pulumi.runtime.test
            def it_creates_the_specified_number_of_readers(sut, reader_count):
                # Verify the primary instance exists
                assert sut.rds_serverless_cluster_instance is not None
                # Verify the correct number of reader instances
                assert len(sut.reader_instances) == reader_count

    def describe_when_given_a_kms_key_to_restore_from():
        @pytest.fixture
        def kms_key(faker):
            return f'arn:aws:kms:us-west-2:448312246740:key/{faker.word()}'

        @pytest.fixture
        def component_kwargs(component_kwargs, kms_key):
            component_kwargs['kms_key_id'] = \
                kms_key
            return component_kwargs

        @pulumi.runtime.test
        def it_encrypts(sut, kms_key):
            return assert_output_equals(sut.rds_serverless_cluster.storage_encrypted,
                                        True)

        @pulumi.runtime.test
        def it_encrypts_with_provided_key(sut, kms_key):
            return assert_output_equals(sut.rds_serverless_cluster.kms_key_id,
                                        kms_key)

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
        def it_sets_apply_immediately(sut):
            return assert_output_equals(sut.rds_serverless_cluster_instance.apply_immediately, True)

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

        def describe_with_a_custom_namespace():
            @pytest.fixture
            def namespace(faker):
                return f'{faker.word()}-{faker.word()}'

            @pytest.fixture
            def component_kwargs(component_kwargs, namespace):
                component_kwargs['namespace'] = namespace
                return component_kwargs

            @pulumi.runtime.test
            def it_creates_a_cluster_instance_with_an_overridden_namespace(sut, namespace):
                return assert_output_equals(sut.rds_serverless_cluster_instance.identifier, namespace)

        @pulumi.runtime.test
        def it_is_publicly_accessible(sut, app_name):
            return assert_output_equals(sut.rds_serverless_cluster_instance.publicly_accessible, True)

    def describe_an_ecs_cluster():
        @pulumi.runtime.test
        def it_creates_a_cluster(sut, app_name, stack):
            return assert_output_equals(sut.ecs_cluster.name, f"{app_name}-{stack}")

        def describe_with_a_custom_namespace():
            @pytest.fixture
            def namespace(faker):
                return f'{faker.word()}-{faker.word()}'

            @pytest.fixture
            def component_kwargs(component_kwargs, namespace):
                component_kwargs['namespace'] = namespace
                return component_kwargs

            @pulumi.runtime.test
            def it_creates_a_cluster_with_an_overridden_namespace(sut, namespace):
                return assert_output_equals(sut.ecs_cluster.name, namespace)

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

        @pulumi.runtime.test
        def it_uses_rails_command(sut, container_cmd):
            assert sut.web_container.command == container_cmd

        @pulumi.runtime.test
        def it_uses_empty_entry_point_for_execution(sut):
            assert sut.migration_container.entry_point == []

        @pulumi.runtime.test
        def it_uses_standard_migration_command_for_execution(sut, execution_container_cmd):
            assert sut.migration_container.command == execution_container_cmd

        def describe_with_custom_execution_cmd():
            @pytest.fixture
            def execution_container_cmd():
                return ["sh", "-c", "bundle exec rails db:migrate"]

            @pytest.fixture
            def component_kwargs(component_kwargs, execution_container_cmd):
                component_kwargs['execution_cmd'] = execution_container_cmd
                return component_kwargs

            @pulumi.runtime.test
            def it_uses_custom_command_for_execution(sut, execution_container_cmd):
                assert sut.migration_container.command == execution_container_cmd

    @pulumi.runtime.test
    def it_allows_container_to_talk_to_rds(sut, ecs_security_groups):
        assert sut.firewall_rule
        return assert_outputs_equal(sut.firewall_rule.security_group_id,
                                    sut.rds_serverless_cluster.vpc_security_group_ids[0]) \
            and assert_output_equals(sut.firewall_rule.source_security_group_id, ecs_security_groups[0])

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

        @pulumi.runtime.test
        def it_sets_process_type_env_var_for_worker_container(sut):
            assert sut.worker_container.env_vars["PROCESS_TYPE"] == "worker"

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

        def describe_with_a_custom_namespace():
            @pytest.fixture
            def namespace(faker):
                return f'{faker.word()}-{faker.word()}-namespace'

            @pytest.fixture
            def component_kwargs(component_kwargs, namespace):
                component_kwargs['namespace'] = namespace
                return component_kwargs

            @pulumi.runtime.test
            def it_creates_a_queue_redis_with_custom_namespace(sut, namespace):
                return assert_output_equals(sut.queue_redis.cluster.cluster_id, f'{namespace}-queue-redis')

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

        def describe_with_a_custom_namespace():
            @pytest.fixture
            def namespace(faker):
                return f'{faker.word()}-{faker.word()}-namespace'

            @pytest.fixture
            def component_kwargs(component_kwargs, namespace):
                component_kwargs['namespace'] = namespace
                return component_kwargs

            @pulumi.runtime.test
            def it_creates_a_cache_redis_with_custom_namespace(sut, namespace):
                return assert_output_equals(sut.cache_redis.cluster.cluster_id, f'{namespace}-cache-redis')

        @pulumi.runtime.test
        def it_sends_the_url_to_the_ecs_environment(sut):
            return assert_outputs_equal(sut.env_vars["CACHE_REDIS_URL"], sut.cache_redis.url)

        @pulumi.runtime.test
        def it_sends_the_url_to_the_ecs_environment(sut):
            return assert_outputs_equal(sut.env_vars["REDIS_SERVER"], sut.cache_redis.url)

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

    def describe_with_autoscale_off():
        @pytest.fixture
        def component_kwargs(component_kwargs):
            component_kwargs['autoscale'] = False

            return component_kwargs

        @pulumi.runtime.test
        def it_does_not_create_autoscale(sut):
            assert sut.web_container.autoscaling_target is None

    def describe_with_worker_autoscale_off():
        @pytest.fixture
        def component_kwargs(component_kwargs):
            component_kwargs['need_worker'] = True
            component_kwargs['worker_autoscale'] = False

            return component_kwargs

        @pulumi.runtime.test
        def it_does_not_create_worker_autoscale(sut):
            assert sut.worker_container.worker_autoscaling is None

    def describe_with_a_custom_namespace():
        @pytest.fixture
        def namespace(faker):
            return f'{faker.word()}-{faker.word()}-namespace'

        @pytest.fixture
        def component_kwargs(component_kwargs, namespace):
            component_kwargs['namespace'] = namespace
            return component_kwargs

        @pulumi.runtime.test
        def it_creates_secrets_with_the_namespace(sut, namespace):
            assert sut.secret.namespace == namespace


    @pulumi.runtime.test
    def it_sets_the_desired_web_count(sut):
        def check_desired_count(args):
            desired_count = args[0]
            assert sut.current_desired_count == desired_count
            return True
        return pulumi.Output.all(sut.web_container.fargate_service.desired_count).apply(check_desired_count)

    def describe_with_rds_proxy_enabled():
        @pytest.fixture
        def component_kwargs(component_kwargs):
            component_kwargs['enable_rds_proxy'] = True
            return component_kwargs

        @pulumi.runtime.test
        def it_creates_an_rds_proxy(sut):
            assert sut.rds_proxy is not None

        @pulumi.runtime.test
        def it_creates_proxy_secret(sut):
            assert sut.proxy_secret is not None

        @pulumi.runtime.test
        def it_creates_proxy_role(sut):
            assert sut.proxy_role is not None

        @pulumi.runtime.test
        def it_creates_proxy_target_group(sut):
            assert sut.proxy_default_target_group is not None

        @pulumi.runtime.test
        def it_creates_proxy_target(sut):
            assert sut.proxy_target is not None

        @pulumi.runtime.test
        def it_creates_elt_reader_secret(sut):
            assert sut.proxy_elt_reader_secret is not None

        @pulumi.runtime.test
        def it_adds_proxy_endpoint_to_env_vars(sut):
            assert 'RDS_PROXY_ENDPOINT' in sut.web_container.env_vars

        @pulumi.runtime.test
        def it_does_not_create_readonly_endpoint_without_readers(sut):
            assert sut.proxy_readonly_endpoint is None

        @pulumi.runtime.test
        def it_does_not_add_readonly_endpoint_to_env_vars_without_readers(sut):
            assert 'RDS_PROXY_READONLY_ENDPOINT' not in sut.web_container.env_vars

        def describe_with_reader_instances():
            @pytest.fixture
            def reader_count():
                return 2

            @pytest.fixture
            def component_kwargs(component_kwargs, reader_count):
                component_kwargs['reader_instance_count'] = reader_count
                return component_kwargs

            @pulumi.runtime.test
            def it_creates_reader_instances(sut, reader_count):
                assert len(sut.reader_instances) == reader_count

            @pulumi.runtime.test
            def it_creates_readonly_endpoint(sut):
                assert sut.proxy_readonly_endpoint is not None

            @pulumi.runtime.test
            def it_adds_readonly_endpoint_to_env_vars(sut):
                assert 'RDS_PROXY_READONLY_ENDPOINT' in sut.web_container.env_vars

            @pulumi.runtime.test
            def it_adds_both_proxy_endpoints_to_env_vars(sut):
                assert 'RDS_PROXY_ENDPOINT' in sut.web_container.env_vars
                assert 'RDS_PROXY_READONLY_ENDPOINT' in sut.web_container.env_vars

    def describe_rds_tags():
        @pulumi.runtime.test
        def it_applies_default_tags_to_rds_cluster(sut, app_name, stack, environment):
            def check_tags(tags):
                assert tags['product'] == app_name
                assert tags['repository'] == app_name
                assert tags['service'] == app_name
                assert tags['environment'] == environment
                assert 'owner' in tags
                return True
            
            return sut.rds_serverless_cluster.tags.apply(check_tags)

        @pulumi.runtime.test
        def it_applies_default_tags_to_rds_instance(sut, app_name, environment):
            def check_tags(tags):
                assert tags['product'] == app_name
                assert tags['environment'] == environment
                return True
            
            return sut.rds_serverless_cluster_instance.tags.apply(check_tags)

        def describe_with_custom_rds_tags():
            @pytest.fixture
            def custom_rds_tags():
                return {
                    'datadog_monitor': 'true',
                    'backup_policy': 'daily',
                    'cost_center': 'engineering'
                }

            @pytest.fixture
            def component_kwargs(component_kwargs, custom_rds_tags):
                component_kwargs['rds_tags'] = custom_rds_tags
                return component_kwargs

            @pulumi.runtime.test
            def it_merges_custom_tags_with_default_tags_on_cluster(sut, app_name, custom_rds_tags, environment):
                def check_tags(tags):
                    # Check default tags still exist
                    assert tags['product'] == app_name
                    assert tags['repository'] == app_name
                    assert tags['service'] == app_name
                    assert tags['environment'] == environment
                    # Check custom tags are added
                    assert tags['datadog_monitor'] == 'true'
                    assert tags['backup_policy'] == 'daily'
                    assert tags['cost_center'] == 'engineering'
                    return True
                
                return sut.rds_serverless_cluster.tags.apply(check_tags)

            @pulumi.runtime.test
            def it_merges_custom_tags_with_default_tags_on_instance(sut, app_name, custom_rds_tags, environment):
                def check_tags(tags):
                    # Check default tags still exist
                    assert tags['product'] == app_name
                    assert tags['environment'] == environment
                    # Check custom tags are added
                    assert tags['datadog_monitor'] == 'true'
                    assert tags['backup_policy'] == 'daily'
                    return True
                
                return sut.rds_serverless_cluster_instance.tags.apply(check_tags)

            def describe_with_reader_instances():
                @pytest.fixture
                def reader_count():
                    return 2

                @pytest.fixture
                def component_kwargs(component_kwargs, reader_count):
                    component_kwargs['reader_instance_count'] = reader_count
                    return component_kwargs

                @pulumi.runtime.test
                def it_applies_custom_tags_to_reader_instances(sut, reader_count, custom_rds_tags):
                    def check_reader_tags(reader_index):
                        def check_tags(tags):
                            assert tags['datadog_monitor'] == 'true'
                            assert tags['backup_policy'] == 'daily'
                            return True
                        return sut.reader_instances[reader_index].tags.apply(check_tags)
                    
                    # Check first reader instance
                    return check_reader_tags(0)

            def describe_with_rds_proxy():
                @pytest.fixture
                def component_kwargs(component_kwargs):
                    component_kwargs['enable_rds_proxy'] = True
                    return component_kwargs

                @pulumi.runtime.test
                def it_applies_custom_tags_to_proxy(sut, custom_rds_tags):
                    def check_tags(tags):
                        assert tags['datadog_monitor'] == 'true'
                        assert tags['backup_policy'] == 'daily'
                        return True
                    
                    return sut.rds_proxy.tags.apply(check_tags)

                @pulumi.runtime.test
                def it_applies_custom_tags_to_proxy_secret(sut, custom_rds_tags):
                    def check_tags(tags):
                        assert tags['datadog_monitor'] == 'true'
                        return True
                    
                    return sut.proxy_secret.tags.apply(check_tags)

                @pulumi.runtime.test
                def it_applies_custom_tags_to_proxy_elt_reader_secret(sut, custom_rds_tags):
                    def check_tags(tags):
                        assert tags['datadog_monitor'] == 'true'
                        return True
                    
                    return sut.proxy_elt_reader_secret.tags.apply(check_tags)

                @pulumi.runtime.test
                def it_applies_custom_tags_to_proxy_role(sut, custom_rds_tags):
                    def check_tags(tags):
                        assert tags['datadog_monitor'] == 'true'
                        return True
                    
                    return sut.proxy_role.tags.apply(check_tags)

                def describe_with_reader_instances_and_proxy():
                    @pytest.fixture
                    def reader_count():
                        return 1

                    @pytest.fixture
                    def component_kwargs(component_kwargs, reader_count):
                        component_kwargs['reader_instance_count'] = reader_count
                        return component_kwargs

                    @pulumi.runtime.test
                    def it_applies_custom_tags_to_readonly_endpoint(sut, custom_rds_tags):
                        def check_tags(tags):
                            assert tags['datadog_monitor'] == 'true'
                            return True
                        
                        return sut.proxy_readonly_endpoint.tags.apply(check_tags)

        def describe_with_custom_tags_overriding_defaults():
            @pytest.fixture
            def custom_rds_tags():
                # Intentionally override a default tag
                return {
                    'environment': 'custom-env',
                    'datadog_monitor': 'true'
                }

            @pytest.fixture
            def component_kwargs(component_kwargs, custom_rds_tags):
                component_kwargs['rds_tags'] = custom_rds_tags
                return component_kwargs

            @pulumi.runtime.test
            def it_allows_custom_tags_to_override_defaults(sut, custom_rds_tags):
                def check_tags(tags):
                    # Custom tag should override default
                    assert tags['environment'] == 'custom-env'
                    assert tags['datadog_monitor'] == 'true'
                    return True
                
                return sut.rds_serverless_cluster.tags.apply(check_tags)