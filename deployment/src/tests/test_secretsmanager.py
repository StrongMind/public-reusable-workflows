import os
import json

import pulumi.runtime
import pulumi_aws
import pytest
from pulumi import Output

from tests.shared import assert_outputs_equal, assert_output_equals
from tests.mocks import get_pulumi_mocks


def describe_a_pulumi_secretsmanager_component():
    @pytest.fixture
    def app_name(faker):
        return faker.word()

    @pytest.fixture
    def environment(faker):
        return faker.word()

    @pytest.fixture
    def stack(faker, app_name, environment):
        return f"{environment}"

    @pytest.fixture
    def pulumi_mocks(faker):
        return get_pulumi_mocks(faker)

    @pytest.fixture
    def name(faker):
        return faker.word()

    @pytest.fixture
    def component_arguments():
        return {}

    @pytest.fixture
    def sut(pulumi_set_mocks,
            component_arguments,
            name):
        import strongmind_deployment.secretsmanager

        sut = strongmind_deployment.secretsmanager.SecretsComponent(name,
                                                         **component_arguments
                                                         )
        return sut

    @pulumi.runtime.test
    def it_exists(sut):
        assert sut

    @pulumi.runtime.test
    def it_is_a_component_resource(sut):
        assert isinstance(sut, pulumi.ComponentResource)

    def describe_a_secretsmanager_secret():
        @pulumi.runtime.test
        def it_registers_with_pulumi_with_its_type_string(sut):
            assert sut._type == "strongmind:global_build:commons:secretsmanager"

        @pulumi.runtime.test
        def it_has_a_sm_secret(sut):
            assert sut.sm_secret

        @pulumi.runtime.test
        def it_has_sm_secret_version(sut):
            assert sut.sm_secret_version

        @pulumi.runtime.test
        def it_is_named(sut, name):
            assert sut._name == name

        @pulumi.runtime.test
        def it_has_a_sm_secret_name(sut, name, app_name, stack):
            return assert_output_equals(sut.sm_secret.name, f"{app_name}-{stack}-secrets")

        @pulumi.runtime.test
        def it_has_a_sm_secret_version_secret_string(sut):
            return assert_output_equals(sut.sm_secret_version.secret_string, "{}")

        @pulumi.runtime.test
        def it_has_a_get_secrets_method(sut):
            assert sut.get_secrets

        def descride_get_secrets_method():
            @pytest.fixture
            def secret_string(faker):
                return f"{{\"{faker.word()}\":\"{faker.password()}\"}}"

            @pytest.fixture
            def secret_arn(faker):
                return f"arn:aws:secretsmanager:us-west-2:{faker.random_int()}:secret:{faker.word()}-{faker.random_int()}"

            @pytest.fixture
            def sut(component_arguments,
                    name,
                    secret_string):
                import strongmind_deployment.secretsmanager

                sut = strongmind_deployment.secretsmanager.SecretsComponent(name,
                                                        **component_arguments,
                                                        secret_string=secret_string,
                                                        )
                return sut
            
            @pulumi.runtime.test
            def it_should_return_secrets(sut, secret_string):
                secret_arn = sut.sm_secret.arn
                secrets = sut.get_secrets(secret_arn)
                assert secrets
                assert isinstance(secrets, dict)
                assert len(secrets) > 0
                assert all([a["name"] == b["name"] for a, b in zip(secrets, secret_string)])
                return assert_output_equals(sut._secrets_string, secret_string)
