import os

import pulumi.runtime
import pytest

from strongmind_deployment.alb import AlbPlacement
from tests.mocks import get_pulumi_mocks


def describe_a_application_load_balancer_component():
    @pytest.fixture
    def name(faker):
        return faker.word()

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
    def alb_args(vpc_id, certificate_arn):
        from strongmind_deployment.alb import AlbArgs
        return AlbArgs(
            vpc_id=vpc_id,
            subnets=['subnet-123456', 'subnet-654321'],
            certificate_arn=certificate_arn,
            placement=AlbPlacement.EXTERNAL,
            tags={},
        )

    @pytest.fixture
    def vpc_id():
        return "vpc-123456"

    @pytest.fixture
    def certificate_arn():
        return "arn:aws:acm:us-west-2:123456789012:certificate/12345678-1234-1234-1234-123456789012"

    @pytest.fixture
    def sut(name, alb_args, pulumi_set_mocks):
        from strongmind.alb import Alb
        return Alb(name, alb_args)

    @pulumi.runtime.test
    def it_exists(sut):
        assert sut

    def it_has_a_name(sut, name):
        assert sut._name == name

    def it_has_a_type(sut):
        assert sut._type == "strongmind:global_build:commons:alb"

    def it_has_a_namespace_that_defaults_to_project_stack(sut, app_name, stack):
        assert sut.namespace == f"{app_name}-{stack}"

    def describe_with_a_custom_namespace():
        @pytest.fixture
        def namespace(faker):
            return faker.word()

        @pytest.fixture
        def alb_args(vpc_id, certificate_arn, namespace):
            from strongmind.alb import AlbArgs
            return AlbArgs(
                vpc_id=vpc_id,
                subnets=['subnet-123456', 'subnet-654321'],
                certificate_arn=certificate_arn,
                placement=AlbPlacement.EXTERNAL,
                tags={},
                namespace=namespace,
            )

        @pytest.fixture
        def sut(name, alb_args, pulumi_set_mocks):
            from strongmind.alb import Alb
            return Alb(name, alb_args)

        def it_has_a_custom_namespace(sut, namespace):
            assert sut.namespace == namespace