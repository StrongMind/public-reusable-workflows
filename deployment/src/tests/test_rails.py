import os

import pulumi.runtime
import pytest

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
    def app_path(faker):
        return f'./{faker.word()}'

    @pytest.fixture
    def container_port(faker):
        return faker.random_int()

    @pytest.fixture
    def container_entry_point():
        return ["sh", "-c", "rails db:prepare db:migrate db:seed && "
                            "rails assets:precompile && "
                            "rails server --port 3000 -b 0.0.0.0"]

    @pytest.fixture
    def worker_container_app_path(faker):
        return f'./{faker.word()}'

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
    def redis_node_type():
        return None

    @pytest.fixture
    def redis_num_cache_nodes():
        return None

    @pytest.fixture
    def sut(pulumi_set_mocks,
            app_path,
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
            worker_container_app_path,
            worker_container_entry_point,
            worker_container_cpu,
            worker_container_memory,
            redis_node_type,
            redis_num_cache_nodes):
        import strongmind_deployment.rails

        kwargs = {
            "app_path": app_path,
            "container_port": container_port,
            "cpu": cpu,
            "memory": memory,
            "need_worker": True,
            "worker_entry_point": worker_container_entry_point,
            "worker_app_path": worker_container_app_path,
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
            }
        }
        if redis_node_type:
            kwargs["redis_node_type"] = redis_node_type
        if redis_num_cache_nodes:
            kwargs["redis_num_cache_nodes"] = redis_num_cache_nodes

        sut = strongmind_deployment.rails.RailsComponent("rails",
                                                         **kwargs
                                                         )
        return sut

    def it_exists(sut):
        assert sut

    def describe_a_rds_postgres_cluster():
        @pulumi.runtime.test
        def it_has_a_password(sut):
            assert sut.db_password

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
        def it_sets_the_master_password(sut, master_db_password):
            return assert_output_equals(sut.rds_serverless_cluster.master_password, master_db_password)

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
                sut.rds_serverless_cluster.master_password
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
                sut.rds_serverless_cluster.master_password
            ).apply(check_ecs_environment)

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
                                                 app_path,
                                                 container_port,
                                                 cpu,
                                                 memory):
            def check_machine_specs(args):
                container_app_path, port, container_cpu, container_memory = args
                assert container_app_path == app_path
                assert port == container_port
                assert container_cpu == cpu
                assert container_memory == memory

            return pulumi.Output.all(
                sut.web_container.app_path,
                sut.web_container.container_port,
                sut.web_container.cpu,
                sut.web_container.memory
            ).apply(check_machine_specs)

        @pulumi.runtime.test
        def it_uses_rails_entry_point(sut, container_entry_point):
            assert sut.web_container.entry_point == container_entry_point

        @pulumi.runtime.test
        def it_creates_a_worker_container_component(sut,
                                                    worker_container_app_path,
                                                    worker_container_cpu,
                                                    worker_container_memory):
            def check_machine_specs(args):
                container_app_path, container_cpu, container_memory = args
                assert container_app_path == worker_container_app_path
                assert container_cpu == worker_container_cpu
                assert container_memory == worker_container_memory

            return pulumi.Output.all(
                sut.worker_container.app_path,
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
        assert sut.worker_container.ecs_cluster_arn == sut.web_container.ecs_cluster.arn

    @pulumi.runtime.test
    def it_allows_container_to_talk_to_rds(sut, ecs_security_group):
        assert sut.firewall_rule
        return assert_outputs_equal(sut.firewall_rule.security_group_id,
                                    sut.rds_serverless_cluster.vpc_security_group_ids[0]) \
            and assert_output_equals(sut.firewall_rule.source_security_group_id, ecs_security_group)

    def describe_a_redis_cluster():
        @pulumi.runtime.test
        def it_has_redis(sut):
            assert sut.redis

        @pulumi.runtime.test
        def it_sends_the_redis_cluster_url_to_the_ecs_environment(sut):
            def check_redis_endpoint(args):
                cache_nodes, redis_url = args
                endpoint = cache_nodes[0]['address']
                port = cache_nodes[0]['port']
                expected_redis_url = f'redis://{endpoint}:{port}'
                assert redis_url == expected_redis_url

            return pulumi.Output.all(
                sut.redis.cluster.cache_nodes,
                sut.env_vars["REDIS_URL"]).apply(check_redis_endpoint)

        def describe_redis_cluster_with_scaling_overrides():
            @pytest.fixture
            def redis_node_type():
                return "cache.t3.micro"

            @pytest.fixture
            def redis_num_cache_nodes():
                return 2

            @pulumi.runtime.test
            def it_passes_node_type(sut, redis_node_type):
                assert sut.redis.node_type == redis_node_type

            @pulumi.runtime.test
            def it_passes_node_count(sut, redis_num_cache_nodes):
                assert sut.redis.num_cache_nodes == redis_num_cache_nodes
