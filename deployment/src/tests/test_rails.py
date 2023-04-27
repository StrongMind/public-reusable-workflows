import pulumi.runtime
import pytest

from shared import assert_outputs_equal, assert_output_equals
from tests.mocks import get_pulumi_mocks
import pulumi_aws as aws


def describe_a_pulumi_rails_app():
    @pytest.fixture
    def pulumi_mocks(faker):
        return get_pulumi_mocks(faker)

    @pytest.fixture
    def pulumi_set_mocks(pulumi_mocks):
        pulumi.runtime.set_mocks(
            pulumi_mocks,
            preview=False
        )
        yield True

    @pytest.fixture
    def app_name(faker):
        return f'{faker.word()}-{faker.word()}'

    @pytest.fixture
    def app_path(faker):
        return f'./{faker.word()}'

    @pytest.fixture
    def container_port(faker):
        return faker.random_int()

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
    def sut(pulumi_set_mocks,
            app_name,
            app_path,
            container_port,
            cpu,
            memory,
            ecs_security_group):
        import strongmind_deployment.rails

        sut = strongmind_deployment.rails.RailsComponent(app_name,
                                                         app_path=app_path,
                                                         container_port=container_port,
                                                         cpu=cpu,
                                                         memory=memory,
                                                         container_security_group_id=ecs_security_group,
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
        def it_sets_the_name_to_the_app_name(sut, app_name):
            def check_rds_cluster_name(args):
                rds_serverless_cluster_name = args[0]
                assert rds_serverless_cluster_name == app_name

            return pulumi.Output.all(sut.rds_serverless_cluster.cluster_identifier).apply(check_rds_cluster_name)

        @pulumi.runtime.test
        def it_sets_the_master_username_and_password(sut, app_name):
            def check_rds_cluster_master_username(args):
                master_username, master_password = args
                assert master_username == app_name.replace('-', '_')
                assert master_password

            return pulumi.Output.all(
                sut.rds_serverless_cluster.master_username,
                sut.rds_serverless_cluster.master_password
            ).apply(check_rds_cluster_master_username)

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
                actual_url, endpoint, master_username, master_password = args
                expected_url = f'postgres://{master_username}:{master_password}@{endpoint}:5432/app'

                assert actual_url == expected_url

            return pulumi.Output.all(
                sut.container.env_vars["DATABASE_URL"],
                sut.rds_serverless_cluster.endpoint,
                sut.rds_serverless_cluster.master_username,
                sut.rds_serverless_cluster.master_password
            ).apply(check_ecs_environment)

        @pulumi.runtime.test
        def it_sets_the_rails_environment(sut):
            assert sut.container.env_vars["RAILS_ENV"] == "production"

        @pulumi.runtime.test
        def it_sends_the_cluster_endpoint_to_the_ecs_environment(sut):
            def check_ecs_environment(args):
                actual_host, expected_endpoint = args
                assert actual_host == expected_endpoint

            return pulumi.Output.all(
                sut.container.env_vars["DATABASE_HOST"],
                sut.rds_serverless_cluster.endpoint
            ).apply(check_ecs_environment)

        @pulumi.runtime.test
        def it_sends_the_cluster_username_to_the_ecs_environment(sut):
            def check_ecs_environment(args):
                actual_username, expected_username = args
                assert actual_username == expected_username

            return pulumi.Output.all(
                sut.container.env_vars["DB_USERNAME"],
                sut.rds_serverless_cluster.master_username
            ).apply(check_ecs_environment)

        @pulumi.runtime.test
        def it_sends_the_cluster_password_to_the_ecs_environment(sut):
            def check_ecs_environment(args):
                actual_password, expected_password = args
                assert actual_password == expected_password

            return pulumi.Output.all(
                sut.container.env_vars["DB_PASSWORD"],
                sut.rds_serverless_cluster.master_password
            ).apply(check_ecs_environment)

    def describe_a_rds_postgres_cluster_instance():
        @pulumi.runtime.test
        def it_creates_a_aurora_postgres_cluster_instance(sut, app_name):
            def check_rds_cluster_instance_engine(args):
                cluster_identifier, instance_class = args
                assert cluster_identifier == app_name
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
        def it_has_the_app_name(sut, app_name):
            def check_rds_cluster_instance_identifier(args):
                identifier = args[0]
                assert identifier == app_name

            return pulumi.Output.all(
                sut.rds_serverless_cluster_instance.identifier,
            ).apply(check_rds_cluster_instance_identifier)

    def describe_a_ecs_task():
        @pulumi.runtime.test
        def it_creates_a_container_component(sut,
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
                sut.container.app_path,
                sut.container.container_port,
                sut.container.cpu,
                sut.container.memory
            ).apply(check_machine_specs)

    @pulumi.runtime.test
    def it_allows_container_to_talk_to_rds(sut, faker):
        assert sut.firewall_rule
        ecs_security_group = faker.word()
        sut.container.security_group = ecs_security_group
        assert_outputs_equal(sut.firewall_rule.security_group_id, sut.rds_serverless_cluster.vpc_security_group_ids[0])
        assert_output_equals(sut.firewall_rule.source_security_group_id, ecs_security_group)
