import pulumi
import pytest
import boto3
from botocore.stub import Stubber

from strongmind_deployment.execution import ExecutionResourceProvider, ExecutionResourceInputs


def describe_an_execution_resource_provider():
    # region fixtures
    @pytest.fixture
    def inputs(stubbed_ecs_client):
        return ExecutionResourceInputs(
            cluster="test_ecs_cluster",
            family="family",
            subnets=["subnets"],
            security_groups=["security_groups"],
            ecs_client=stubbed_ecs_client
        )

    @pytest.fixture
    def sut(stubbed_ecs_client):
        from strongmind_deployment.execution import ExecutionResourceProvider
        return ExecutionResourceProvider()

    @pytest.fixture
    def ecs_client(aws_credentials):
        yield boto3.client('ecs')

    @pytest.fixture
    def stubber(ecs_client):
        yield Stubber(ecs_client)

    @pytest.fixture
    def container_exit_code():
        return 0

    @pytest.fixture
    def stubbed_ecs_client(stubber, ecs_client, container_exit_code):
        stubber.add_response(
            'run_task',
            {"tasks": [{"taskArn": "arn"}]},
            {
                "taskDefinition": "family",
                "cluster": "test_ecs_cluster",
                "launchType": "FARGATE",
                "networkConfiguration": {
                    "awsvpcConfiguration": {
                        "subnets": ["subnets"],
                        "securityGroups": ["security_groups"],
                        "assignPublicIp": "ENABLED"
                    }
                },
                "startedBy": "rails-component"
            }
        )
        stubber.add_response('describe_tasks', {"tasks":
            [{
                "lastStatus": "STOPPED",
                "containers": [{
                    "exitCode": container_exit_code,
                }]
            }]
        }
                             )
        stubber.activate()
        yield ecs_client
        stubber.deactivate()

    # endregion fixtures
    def it_is_a_dynamic_resource_provider(sut):
        assert isinstance(sut, pulumi.dynamic.ResourceProvider)

    def it_acts_as_though_it_has_changed(sut):
        # so that we always run the execution
        assert sut.diff("id", {}, {}).changes

    def describe_when_creating():
        @pytest.fixture
        def result(sut: ExecutionResourceProvider, stubbed_ecs_client, inputs):
            return sut.create(inputs=inputs)

        def it_runs_an_ecs_task(result, stubbed_ecs_client, stubber):
            stubber.assert_no_pending_responses()

        def it_returns_a_pulumi_create_result(result):
            assert isinstance(result, pulumi.dynamic.CreateResult)

        def describe_when_the_task_fails():
            @pytest.fixture
            def container_exit_code():
                return 1

            def it_raises_an_exception(sut):
                with pytest.raises(Exception):
                    sut.create({"cluster": "test_ecs_cluster", "family": "family", "subnets": ["subnets"],
                                "security_groups": ["security_groups"]})

    def describe_when_updating():
        @pytest.fixture
        def result(sut: ExecutionResourceProvider, inputs):
            return sut.update("id", {}, inputs)

        def it_runs_an_ecs_task(result, stubbed_ecs_client, stubber):
            stubber.assert_no_pending_responses()

        def it_returns_a_pulumi_update_result(result):
            assert isinstance(result, pulumi.dynamic.UpdateResult)

        def describe_when_the_task_fails():
            @pytest.fixture
            def container_exit_code():
                return 1

            def it_raises_an_exception(sut):
                with pytest.raises(Exception):
                    sut.update("id", {}, {})
