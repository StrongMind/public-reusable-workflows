import pulumi.runtime
import pytest
from pulumi_cloudflare import Record, Zone

from tests.shared import assert_outputs_equal, assert_output_equals
from tests.mocks import get_pulumi_mocks
import pulumi_aws as aws


def describe_a_pulumi_rails_app():
    @pytest.fixture
    def app_name(faker):
        return faker.word()

    @pytest.fixture
    def stack(faker):
        return "dev"

    @pytest.fixture
    def master_db_password(faker):
        return faker.password(length=30)

    @pytest.fixture
    def pulumi_mocks(faker, master_db_password):
        return get_pulumi_mocks(faker, master_db_password)

    @pytest.fixture
    def pulumi_set_mocks(pulumi_mocks, app_name, stack):
        pulumi.runtime.set_mocks(
            pulumi_mocks,
            project=app_name,
            stack=stack,
            preview=False
        )
        yield True

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
    def load_balancer_arn(faker):
        return f"arn:aws:elasticloadbalancing:us-west-2:{faker.random_int()}:loadbalancer/app/{faker.word()}/{faker.random_int()}"

    @pytest.fixture
    def target_group_arn(faker):
        return f"arn:aws:elasticloadbalancing:us-west-2:{faker.random_int()}:targetgroup/{faker.word()}/{faker.random_int()}"

    @pytest.fixture
    def resource_record_name(faker):
        return f"{faker.word()}.{faker.word()}.{faker.word()}"

    @pytest.fixture
    def resource_record_value(faker):
        return f"{faker.word()}.{faker.word()}.{faker.word()}"

    @pytest.fixture
    def domain_validation_options(faker, resource_record_name, resource_record_value):
        class FakeValidationOption:
            def __init__(self, name, value):
                self.resource_record_name = name
                self.resource_record_value = value
            pass
        return [FakeValidationOption(resource_record_name, resource_record_value)]

    @pytest.fixture
    def load_balancer_dns_name(faker):
        return f"{faker.word()}.{faker.word()}.{faker.word()}"

    @pytest.fixture
    def zone_id(faker):
        return faker.word()

    @pytest.fixture
    def environment(faker):
        return faker.word()

    @pytest.fixture
    def sut(pulumi_set_mocks,
            app_path,
            container_port,
            cpu,
            memory,
            ecs_security_group,
            load_balancer_arn,
            target_group_arn,
            domain_validation_options,
            load_balancer_dns_name,
            zone_id,
            environment):
        import strongmind_deployment.rails

        sut = strongmind_deployment.rails.RailsComponent("rails",
                                                         app_path=app_path,
                                                         container_port=container_port,
                                                         cpu=cpu,
                                                         memory=memory,
                                                         container_security_group_id=ecs_security_group,
                                                         load_balancer_arn=load_balancer_arn,
                                                         target_group_arn=target_group_arn,
                                                         domain_validation_options=domain_validation_options,
                                                         load_balancer_dns_name=load_balancer_dns_name,
                                                         zone_id=zone_id,
                                                         env_vars={
                                                             "ENVIRONMENT_NAME": environment
                                                         }
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
        def it_sets_the_name_to_the_app_name(sut, stack):
            return assert_output_equals(sut.rds_serverless_cluster.cluster_identifier, stack)

        @pulumi.runtime.test
        def it_sets_the_master_username(sut, stack):
            return assert_output_equals(sut.rds_serverless_cluster.master_username, stack.replace('-', '_'))

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
        def it_creates_a_aurora_postgres_cluster_instance(sut, stack):
            def check_rds_cluster_instance_engine(args):
                cluster_identifier, instance_class = args
                assert cluster_identifier == stack
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
        def it_has_the_app_name(sut, stack):
            def check_rds_cluster_instance_identifier(args):
                identifier = args[0]
                assert identifier == stack

            return pulumi.Output.all(
                sut.rds_serverless_cluster_instance.identifier,
            ).apply(check_rds_cluster_instance_identifier)

        @pulumi.runtime.test
        def it_is_publicly_accessible(sut, app_name):
            return assert_output_equals(sut.rds_serverless_cluster_instance.publicly_accessible, True)

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
    def it_allows_container_to_talk_to_rds(sut, ecs_security_group):
        assert sut.firewall_rule
        assert_outputs_equal(sut.firewall_rule.security_group_id, sut.rds_serverless_cluster.vpc_security_group_ids[0])
        assert_output_equals(sut.firewall_rule.source_security_group_id, ecs_security_group)

    def describe_dns():
        @pulumi.runtime.test
        def it_has_cname_record(sut):
            assert sut.cname_record

        @pulumi.runtime.test
        def it_has_name_with_environment_prefix(sut, environment, app_name):
            return assert_output_equals(sut.cname_record.name, f"{environment}-{app_name}")

        def describe_in_production():
            @pytest.fixture
            def environment():
                return "prod"

            @pulumi.runtime.test
            def it_has_name_without_prefix(sut, app_name):
                return assert_output_equals(sut.cname_record.name, app_name)

        @pulumi.runtime.test
        def it_has_cname_type(sut):
            return assert_output_equals(sut.cname_record.type, "CNAME")

        @pulumi.runtime.test
        def it_has_zone(sut, zone_id):
            return assert_output_equals(sut.cname_record.zone_id, zone_id)

        @pulumi.runtime.test
        def it_points_to_load_balancer(sut, load_balancer_dns_name):
            return assert_output_equals(sut.cname_record.value, load_balancer_dns_name)