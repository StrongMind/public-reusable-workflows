import os

import pulumi.runtime
import pytest

from tests.mocks import get_pulumi_mocks
from tests.shared import assert_output_equals


def describe_a_pulumi_containerized_app():
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
    def pulumi_mocks(faker):
        return get_pulumi_mocks(faker)

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
    def container_image(aws_account_id, app_name):
        return f"{aws_account_id}.dkr.ecr.us-west-2.amazonaws.com/{app_name}:latest"

    @pytest.fixture
    def env_vars(faker, environment):
        return {
            "ENVIRONMENT_NAME": environment,
        }

    @pytest.fixture
    def load_balancer_arn(faker):
        return f"arn:aws:elasticloadbalancing:us-west-2:{faker.random_int()}:loadbalancer/app/{faker.word()}/{faker.random_int()}"

    @pytest.fixture
    def target_group_arn(faker):
        return f"arn:aws:elasticloadbalancing:us-west-2:{faker.random_int()}:targetgroup/{faker.word()}/{faker.random_int()}"

    @pytest.fixture
    def zone_id(faker):
        return faker.word()

    @pytest.fixture
    def load_balancer_dns_name(faker):
        return f"{faker.word()}.{faker.word()}.{faker.word()}"

    @pytest.fixture
    def resource_record_name(faker):
        return f"{faker.word()}.{faker.word()}.{faker.word()}"

    @pytest.fixture
    def resource_record_value(faker):
        return f"{faker.word()}.{faker.word()}.{faker.word()}"

    @pytest.fixture
    def resource_record_type(faker):
        return faker.word()

    @pytest.fixture
    def domain_validation_options(faker, resource_record_name, resource_record_value, resource_record_type):
        class FakeValidationOption:
            def __init__(self, name, value, type):
                self.resource_record_name = name
                self.resource_record_value = value
                self.resource_record_type = type
            pass
        return [FakeValidationOption(resource_record_name, resource_record_value, resource_record_type)]

    @pytest.fixture
    def sut(pulumi_set_mocks,
            app_name,
            app_path,
            container_port,
            cpu,
            memory,
            container_image,
            env_vars,
            load_balancer_arn,
            target_group_arn,
            zone_id,
            load_balancer_dns_name,
            domain_validation_options,
            ):
        import strongmind_deployment.container
        return strongmind_deployment.container.ContainerComponent("container",
                                                                  app_path=app_path,
                                                                  container_port=container_port,
                                                                  cpu=cpu,
                                                                  memory=memory,
                                                                  container_image=container_image,
                                                                  env_vars=env_vars,
                                                                  load_balancer_arn=load_balancer_arn,
                                                                  target_group_arn=target_group_arn,
                                                                  zone_id=zone_id,
                                                                  load_balancer_dns_name=load_balancer_dns_name,
                                                                  domain_validation_options=domain_validation_options,
                                                                  )

    def it_exists(sut):
        assert sut

    def describe_a_container_component():
        @pulumi.runtime.test
        def it_creates_an_ecs_cluster(sut):
            assert sut.ecs_cluster

        @pulumi.runtime.test
        def it_sets_the_cluster_name(sut, stack):
            def check_cluster_name(args):
                cluster_name = args[0]
                assert cluster_name == stack

            return pulumi.Output.all(sut.ecs_cluster.name).apply(check_cluster_name)

        @pulumi.runtime.test
        def it_has_environment_variables(sut, app_name, env_vars):
            assert sut.env_vars == env_vars

        @pulumi.runtime.test
        def it_creates_a_load_balancer(sut):
            assert sut.load_balancer

        @pulumi.runtime.test
        def it_sets_the_load_balancer_name(sut, stack):
            return assert_output_equals(sut.load_balancer.name, stack)

        @pulumi.runtime.test
        def describe_the_fargate_service():
            @pulumi.runtime.test
            def it_creates_a_fargate_service(sut):
                assert sut.fargate_service

            @pulumi.runtime.test
            def it_has_the_cluster(sut):
                # arn is None at design time so this test doesn't really work
                def check_cluster(args):
                    service_cluster, cluster = args
                    assert service_cluster == cluster

                return pulumi.Output.all(sut.fargate_service.cluster,
                                         sut.ecs_cluster.arn).apply(check_cluster)

            @pulumi.runtime.test
            def it_has_task_definition(sut, container_port, cpu, memory, stack):
                def check_task_definition(args):
                    task_definition_dict = args[0]
                    container = task_definition_dict["container"]
                    assert container["cpu"] == cpu
                    assert container["memory"] == memory
                    assert container["essential"]
                    assert container["portMappings"][0]["containerPort"] == container_port
                    assert container["portMappings"][0]["hostPort"] == container_port
                    assert container["logConfiguration"]["logDriver"] == "awslogs"
                    assert container["logConfiguration"]["options"]["awslogs-group"] == f"/aws/ecs/{stack}"
                    assert container["logConfiguration"]["options"]["awslogs-region"] == "us-west-2"
                    assert container["logConfiguration"]["options"]["awslogs-stream-prefix"] == "container"

                return pulumi.Output.all(sut.fargate_service.task_definition_args).apply(check_task_definition)

            @pulumi.runtime.test
            def it_sends_env_vars_to_the_task_definition(sut, env_vars):
                def check_env_vars(args):
                    task_definition_dict = args[0]
                    env_var_key_value_pair_array = []
                    for var in env_vars:
                        env_var_key_value_pair_array.append({
                            "name": var,
                            "value": env_vars[var]
                        })
                    assert task_definition_dict["container"]["environment"] == env_var_key_value_pair_array

                return pulumi.Output.all(sut.fargate_service.task_definition_args).apply(check_env_vars)

            @pulumi.runtime.test
            def it_sets_the_image(sut, container_image):
                def check_image_tag(args):
                    task_definition_container_image = args[0]
                    assert task_definition_container_image == container_image

                return pulumi.Output.all(sut.fargate_service.task_definition_args["container"]["image"]).apply(
                    check_image_tag)

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

    def describe_cert():
        @pulumi.runtime.test
        def it_has_cert(sut):
            assert sut.cert

        @pulumi.runtime.test
        def it_has_fqdn(sut, load_balancer_dns_name):
            return assert_output_equals(sut.cert.domain_name, load_balancer_dns_name)

        @pulumi.runtime.test
        def it_validates_with_dns(sut):
            return assert_output_equals(sut.cert.validation_method, "DNS")

        @pulumi.runtime.test
        def it_adds_validation_record(sut):
            assert sut.cert_validation_record

        @pulumi.runtime.test
        def it_adds_validation_record_with_name(sut, resource_record_name):
            return assert_output_equals(sut.cert_validation_record.name, resource_record_name)

        @pulumi.runtime.test
        def it_adds_validation_record_with_type(sut):
            return assert_output_equals(sut.cert_validation_record.type, resource_record_type)

        @pulumi.runtime.test
        def it_adds_validation_record_with_zone_id(sut, zone_id):
            return assert_output_equals(sut.cert_validation_record.zone_id, zone_id)

        @pulumi.runtime.test
        def it_adds_validation_record_with_value(sut, resource_record_value):
            return assert_output_equals(sut.cert_validation_record.value, resource_record_value)

        @pulumi.runtime.test
        def it_adds_validation_record_with_ttl(sut):
            return assert_output_equals(sut.cert_validation_record.ttl, 1)
