import os

import pulumi.runtime
import pytest

from tests.mocks import get_pulumi_mocks


def describe_a_pulumi_containerized_app():
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
    def container_image(aws_account_id, app_name):
        return f"{aws_account_id}.dkr.ecr.us-west-2.amazonaws.com/{app_name}:latest"

    @pytest.fixture
    def env_vars(faker):
        return {
            faker.word(): faker.word()
        }

    @pytest.fixture
    def get_aws_account_and_region_mock(aws_account_id):
        def func():
            return str(aws_account_id), "us-west-2"
        return func

    @pytest.fixture
    def sut(pulumi_set_mocks, app_name, app_path, container_port, cpu, memory, container_image, env_vars):
        import strongmind_deployment.container
        return strongmind_deployment.container.ContainerComponent(app_name,
                                                                  app_path=app_path,
                                                                  container_port=container_port,
                                                                  cpu=cpu,
                                                                  memory=memory,
                                                                  container_image=container_image,
                                                                  env_vars=env_vars
                                                                  )

    def it_exists(sut):
        assert sut

    def describe_a_container_component():
        @pulumi.runtime.test
        def it_creates_an_ecs_cluster(sut):
            assert sut.ecs_cluster

        @pulumi.runtime.test
        def it_sets_the_cluster_name(sut, app_name):
            def check_cluster_name(args):
                cluster_name = args[0]
                assert cluster_name == app_name

            return pulumi.Output.all(sut.ecs_cluster.name).apply(check_cluster_name)

        @pulumi.runtime.test
        def it_has_environment_variables(sut, app_name, env_vars):
            assert sut.env_vars == env_vars

        @pulumi.runtime.test
        def it_creates_a_load_balancer(sut):
            assert sut.load_balancer

        @pulumi.runtime.test
        def it_sets_the_load_balancer_name(sut, app_name):
            def check_load_balancer_name(args):
                load_balancer_name = args[0]
                assert load_balancer_name == app_name

            return pulumi.Output.all(sut.load_balancer.name).apply(check_load_balancer_name)

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
            def it_has_task_definition(sut, container_port, cpu, memory):
                def check_task_definition(args):
                    task_definition_dict = args[0]
                    assert task_definition_dict["container"]["cpu"] == cpu
                    assert task_definition_dict["container"]["memory"] == memory
                    assert task_definition_dict["container"]["essential"]
                    assert task_definition_dict["container"]["portMappings"][0]["containerPort"] == container_port
                    assert task_definition_dict["container"]["portMappings"][0]["hostPort"] == container_port

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
