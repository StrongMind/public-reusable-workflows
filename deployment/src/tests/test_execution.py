import pulumi
import pytest
import boto3
import moto


def describe_an_execution_component():
    @pytest.fixture
    def sut():
        from strongmind_deployment.execution import ExecutionComponent
        return ExecutionComponent("provider", "name", {})

    def it_is_a_dynamic_resource(sut):
        assert isinstance(sut, pulumi.dynamic.Resource)

    @pytest.skip("Not implemented")
    def it_uses_the_resource_provider(sut):
        pass


def describe_an_execution_resource_provider():
    @pytest.fixture
    def ecs_cluster(ecs_client):
        return ecs_client.create_cluster(clusterName="test_ecs_cluster")

    @pytest.fixture
    def sut(ecs_client, ecs_cluster):
        from strongmind_deployment.execution import ExecutionResourceProvider
        return ExecutionResourceProvider(ecs_client=ecs_client)

    @pytest.fixture
    def ecs_client(aws_credentials):
        with moto.mock_ecs():
            yield boto3.client('ecs')

    def it_is_a_dynamic_resource_provider(sut):
        assert isinstance(sut, pulumi.dynamic.ResourceProvider)

    def it_acts_as_though_it_has_changed(sut):
        # so that we always run the execution
        assert sut.diff("id", {}, {}).changes == True

    def describe_when_creating():
        @pytest.fixture
        def result(sut):
            return sut.create({"cluster": "test_ecs_cluster", "family": "family", "subnets": ["subnets"],
                               "security_groups": ["security_groups"]})

        @pytest.fixture
        def running_tasks(result, ecs_client, sut):
            return ecs_client.list_tasks(cluster="test_ecs_cluster")['taskArns']

        def it_runs_an_ecs_task(running_tasks):
            assert running_tasks
