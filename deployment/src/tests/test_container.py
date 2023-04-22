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
    def repo_url(aws_account_id, app_name):
        return f"{aws_account_id}.dkr.ecr.us-west-2.amazonaws.com/{app_name}"

    @pytest.fixture
    def get_aws_account_and_region_mock(aws_account_id):
        def func():
            return str(aws_account_id), "us-west-2"
        return func

    @pytest.fixture
    def sut(pulumi_set_mocks, app_name, app_path, container_port, cpu, memory, get_aws_account_and_region_mock):
        import strongmind_deployment.container
        return strongmind_deployment.container.ContainerComponent(app_name,
                                                                  app_path=app_path,
                                                                  container_port=container_port,
                                                                  cpu=cpu,
                                                                  memory=memory,
                                                                  get_aws_account_and_region=get_aws_account_and_region_mock)

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

            def describe_when_image_tag_is_on_the_environment():
                @pytest.fixture
                def image_tag(faker, app_name):
                    os.environ['IMAGE_TAG'] = f"{app_name}:{faker.uuid4()}"
                    return os.environ['IMAGE_TAG']

                @pytest.fixture
                def sut(pulumi_set_mocks, app_name, app_path, image_tag, get_aws_account_and_region_mock):
                    import strongmind_deployment.container
                    return strongmind_deployment.container.ContainerComponent(app_name,
                                                                              app_path=app_path,
                                                                              get_aws_account_and_region=get_aws_account_and_region_mock)


                @pulumi.runtime.test
                def it_sets_the_image_tag_from_the_environment(sut, image_tag, repo_url):
                    def check_image_tag(args):
                        task_definition_container_image = args[0]
                        assert task_definition_container_image == f'{repo_url}/{image_tag}'

                    return pulumi.Output.all(sut.fargate_service.task_definition_args["container"]["image"]).apply(check_image_tag)

            def describe_when_image_tag_is_not_on_the_environment():
                @pytest.fixture
                def image_tag(faker, app_name):
                    if 'IMAGE_TAG' in os.environ:
                        os.environ.pop('IMAGE_TAG')

                @pytest.fixture
                def sut(pulumi_set_mocks, app_name, app_path, image_tag, get_aws_account_and_region_mock):
                    import strongmind_deployment.container
                    return strongmind_deployment.container.ContainerComponent(app_name,
                                                                              app_path=app_path,
                                                                              get_aws_account_and_region=get_aws_account_and_region_mock)

                @pulumi.runtime.test
                def it_sets_the_image_tag_to_the_app_name_plus_latest(sut, app_name, repo_url):
                    def check_image_tag(args):
                        task_definition_container_image = args[0]
                        assert task_definition_container_image == f'{repo_url}/{app_name}:latest'

                    return pulumi.Output.all(sut.fargate_service.task_definition_args["container"]["image"]).apply(
                        check_image_tag)
