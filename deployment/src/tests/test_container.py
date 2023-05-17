import os

import pulumi.runtime
import pytest

from tests.mocks import get_pulumi_mocks
from tests.shared import assert_output_equals, assert_outputs_equal


def describe_a_pulumi_containerized_app():
    @pytest.fixture
    def app_name(faker):
        return faker.word()

    @pytest.fixture
    def environment(faker):
        os.environ["ENVIRONMENT_NAME"] = faker.word()
        return os.environ["ENVIRONMENT_NAME"]

    @pytest.fixture
    def stack(environment):
        return environment

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
    def entry_point(faker):
        return f'./{faker.word()}'

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
            entry_point,
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
                                                                  entry_point=entry_point,
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
        def it_sets_the_cluster_name(sut, stack, app_name):
            def check_cluster_name(args):
                cluster_name = args[0]
                assert cluster_name == f"{app_name}-{stack}"

            return pulumi.Output.all(sut.ecs_cluster.name).apply(check_cluster_name)

        @pulumi.runtime.test
        def it_has_environment_variables(sut, app_name, env_vars):
            assert sut.env_vars == env_vars

        def describe_load_balancer():
            @pulumi.runtime.test
            def it_creates_a_load_balancer(sut):
                assert sut.load_balancer

            @pulumi.runtime.test
            def it_sets_the_load_balancer_name(sut, stack, app_name):
                return assert_output_equals(sut.load_balancer.name, f"{app_name}-{stack}")

            def describe_target_group():
                @pulumi.runtime.test
                def it_sets_the_target_group_port(sut, container_port):
                    return assert_output_equals(sut.target_group.port, container_port)

                @pulumi.runtime.test
                def it_sets_the_target_group_target_type(sut):
                    return assert_output_equals(sut.target_group.target_type, "ip")

                @pulumi.runtime.test
                def it_sets_the_target_group_health_check_enabled(sut):
                    return assert_output_equals(sut.target_group.health_check.enabled, True)

                @pulumi.runtime.test
                def it_sets_the_target_group_health_check_healthy_threshold(sut):
                    return assert_output_equals(sut.target_group.health_check.healthy_threshold, 5)

                @pulumi.runtime.test
                def it_sets_the_target_group_health_check_unhealthy_threshold(sut):
                    return assert_output_equals(sut.target_group.health_check.unhealthy_threshold, 2)

                @pulumi.runtime.test
                def it_sets_the_target_group_health_check_interval(sut):
                    return assert_output_equals(sut.target_group.health_check.interval, 30)

                @pulumi.runtime.test
                def it_sets_the_target_group_health_check_matcher_to_200(sut):
                    return assert_output_equals(sut.target_group.health_check.matcher, "200")

                @pulumi.runtime.test
                def it_sets_the_target_group_health_check_path_to_up(sut):
                    return assert_output_equals(sut.target_group.health_check.path, "/up")

                @pulumi.runtime.test
                def it_sets_the_target_group_health_check_protocol(sut):
                    return assert_output_equals(sut.target_group.health_check.protocol, "HTTP")

                @pulumi.runtime.test
                def it_sets_the_target_group_health_check_timeout(sut):
                    return assert_output_equals(sut.target_group.health_check.timeout, 5)

            def describe_the_load_balancer_listener_for_https():
                @pytest.fixture
                def listener(sut):
                    return sut.load_balancer_listener

                @pulumi.runtime.test
                def it_has_load_balancer_listener_for_https(listener):
                    assert listener

                @pulumi.runtime.test
                def it_sets_the_load_balancer_arn(listener, load_balancer_arn):
                    return assert_output_equals(listener.load_balancer_arn, load_balancer_arn)

                @pulumi.runtime.test
                def it_sets_the_certificate_arn(listener, sut):
                    return assert_outputs_equal(listener.certificate_arn, sut.cert.arn)

                @pulumi.runtime.test
                def it_sets_the_port(listener):
                    return assert_output_equals(listener.port, 443)

                @pulumi.runtime.test
                def it_sets_the_protocol(listener):
                    return assert_output_equals(listener.protocol, "HTTPS")

                @pulumi.runtime.test
                def it_forwards_to_the_target_group(listener, target_group_arn):
                    return assert_output_equals(listener.default_actions[0].target_group_arn, target_group_arn)

                @pulumi.runtime.test
                def it_forwards(listener):
                    return assert_output_equals(listener.default_actions[0].type, "forward")

            def describe_the_load_balancer_listener_for_http():
                @pytest.fixture
                def listener(sut):
                    return sut.load_balancer_listener_redirect_http_to_https

                @pulumi.runtime.test
                def it_has_load_balancer_listener_for_http(listener):
                    assert listener

                @pulumi.runtime.test
                def it_sets_the_load_balancer_arn(listener, load_balancer_arn):
                    return assert_output_equals(listener.load_balancer_arn, load_balancer_arn)

                @pulumi.runtime.test
                def it_sets_the_port(listener):
                    return assert_output_equals(listener.port, 80)

                @pulumi.runtime.test
                def it_sets_the_protocol(listener):
                    return assert_output_equals(listener.protocol, "HTTP")

                @pytest.fixture
                def redirect_action(listener):
                    return listener.default_actions[0]

                @pulumi.runtime.test
                def it_redirects_to_443(redirect_action):
                    return assert_output_equals(redirect_action.redirect.port, "443")

                @pulumi.runtime.test
                def it_redirects_to_https(redirect_action):
                    return assert_output_equals(redirect_action.redirect.protocol, "HTTPS")

                @pulumi.runtime.test
                def it_redirects_with_301(redirect_action):
                    return assert_output_equals(redirect_action.redirect.status_code, "HTTP_301")

                @pulumi.runtime.test
                def it_redirects(redirect_action):
                    return assert_output_equals(redirect_action.type, "redirect")


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
            def it_has_task_definition(sut, container_port, cpu, memory, entry_point, stack, app_name):
                def check_task_definition(args):
                    task_definition_dict = args[0]
                    container = task_definition_dict["container"]
                    assert container["cpu"] == cpu
                    assert container["memory"] == memory
                    assert container["essential"]
                    assert container["entryPoint"] == entry_point
                    assert container["portMappings"][0]["containerPort"] == container_port
                    assert container["portMappings"][0]["hostPort"] == container_port
                    assert container["logConfiguration"]["logDriver"] == "awslogs"
                    assert container["logConfiguration"]["options"]["awslogs-group"] == f"/aws/ecs/{app_name}-{stack}"
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
        def it_has_name_with_environment_prefix(sut, stack, app_name):
            return assert_output_equals(sut.cname_record.name, f"{stack}-{app_name}")

        def describe_in_production():
            @pytest.fixture
            def environment():
                os.environ["ENVIRONMENT_NAME"] = "prod"
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
        def it_has_fqdn(sut, app_name, environment):
            return assert_output_equals(sut.cert.domain_name, f"{environment}-{app_name}.strongmind.com")

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
        def it_adds_validation_record_with_type(sut, resource_record_type):
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

        @pulumi.runtime.test
        def it_adds_validation_cert(sut):
            assert sut.cert_validation_cert

        @pulumi.runtime.test
        def it_adds_validation_cert_with_cert_arn(sut):
            return assert_outputs_equal(sut.cert_validation_cert.certificate_arn, sut.cert.arn)

        @pulumi.runtime.test
        def it_adds_validation_cert_with_fqdns(sut):
            return assert_outputs_equal(sut.cert_validation_cert.validation_record_fqdns,
                                        [sut.cert_validation_record.hostname])
