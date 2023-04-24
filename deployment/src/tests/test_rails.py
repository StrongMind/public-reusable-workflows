import pulumi.runtime
import pytest

from tests.mocks import get_pulumi_mocks


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
    def sut(pulumi_set_mocks,
            app_name,
            app_path,
            container_port,
            cpu,
            memory):
        import strongmind_deployment.rails

        def func():
            return str(aws_account_id), "us-west-2"

        return strongmind_deployment.rails.RailsComponent(app_name,
                                                          app_path=app_path,
                                                          container_port=container_port,
                                                          cpu=cpu,
                                                          memory=memory
                                                          )

    def it_exists(sut):
        assert sut

    def describe_a_rds_postgres_cluster():
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
        def it_sends_the_cluster_endpoint_to_the_ecs_environment(sut):
            def check_ecs_environment(args):
                cluster_endpoint = args[0]
                assert cluster_endpoint

            return pulumi.Output.all(
                sut.container.fargate_service.task_definition_args
            )

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
