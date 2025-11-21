import json
import os
import random

import pulumi.runtime
import pytest

from strongmind_deployment.operations import get_code_owner_team_name
from tests.mocks import get_pulumi_mocks
from strongmind_deployment.lambda_component import LambdaComponent, LambdaArgs, LambdaEnvVariables
from tests.shared import assert_outputs_equal, assert_output_equals


def describe_lambda_args():
    @pytest.fixture
    def handler(faker):
        return faker.word()

    @pytest.fixture
    def runtime(faker):
        valid_runtimes = [
            "python3.9",
            "python3.10",
            "python3.11",
        ]
        return random.choice(valid_runtimes)

    @pytest.fixture
    def timeout(faker):
        return faker.random_int()

    @pytest.fixture
    def memory_size(faker):
        return faker.random_int()

    @pytest.fixture
    def layers(faker):
        return [faker.word(), faker.word()]

    @pytest.fixture
    def sut(handler, runtime, timeout, memory_size, layers):
        return LambdaArgs(
            handler=handler,
            runtime=runtime,
            timeout=timeout,
            memory_size=memory_size,
            layers=layers,
        )

    @pulumi.runtime.test
    def it_exists(sut):
        assert sut

    @pulumi.runtime.test
    def it_has_a_handler(sut, handler):
        assert sut.handler == handler

    @pulumi.runtime.test
    def it_has_a_runtime(sut, runtime):
        assert sut.runtime == runtime

    @pulumi.runtime.test
    def it_has_a_timeout(sut, timeout):
        assert sut.timeout == timeout

    @pulumi.runtime.test
    def it_has_a_memory_size(sut, memory_size):
        assert sut.memory_size == memory_size

    @pulumi.runtime.test
    def it_has_layers(sut, layers):
        assert sut.layers == layers


def describe_lambda_environment():
    @pytest.fixture
    def variables(faker):
        return {faker.word(): faker.word()}

    @pytest.fixture
    def sut(variables):
        return LambdaEnvVariables(variables)

    @pulumi.runtime.test
    def it_exists(sut):
        assert sut

    @pulumi.runtime.test
    def it_has_a_dict_of_variables(sut):
        assert isinstance(sut.variables, dict)

    @pulumi.runtime.test
    def it_has_lambda_env_variables(sut, variables):
        assert sut.variables == variables

def describe_a_lambda_component():
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
    def runtime(faker):
        valid_runtimes = [
            "python3.9",
            "python3.10",
            "python3.11",
        ]
        return random.choice(valid_runtimes)

    @pytest.fixture
    def lambda_args(faker, runtime):
        return LambdaArgs(
            handler=faker.word(),
            runtime=runtime,
            timeout=faker.random_int(),
            memory_size=faker.random_int(),
            layers=[faker.word(), faker.word()],
        )

    @pytest.fixture
    def lambda_env_variables(faker):
        return LambdaEnvVariables(variables={faker.word(): faker.word()})

    @pytest.fixture
    def sut(name, lambda_args, lambda_env_variables, pulumi_set_mocks):
        return LambdaComponent(name, lambda_args, lambda_env_variables)

    @pytest.fixture
    def tags(app_name, environment):
        return {
            "product": app_name,
            "repository": app_name,
            "service": app_name,
            "environment": environment,
            "owner": get_code_owner_team_name()
        }

    @pulumi.runtime.test
    def it_exists(sut):
        assert sut

    @pulumi.runtime.test
    def it_has_a_name(sut, name):
        assert sut.name == name

    @pulumi.runtime.test
    def it_has_a_namespace(sut, app_name, stack):
        assert sut.namespace == f"{app_name}-{stack}"

    @pulumi.runtime.test
    def it_sets_the_owning_team(sut):
        assert sut.owning_team == get_code_owner_team_name()

    @pulumi.runtime.test
    def it_has_tags(sut, app_name, environment, tags):
        assert sut.tags == tags

    @pulumi.runtime.test
    def it_has_lambda_env_variables(sut, lambda_env_variables):
        assert sut.lambda_env_variables == lambda_env_variables

    def describe_a_lambda_role():
        @pytest.fixture
        def assume_role_policy():
            return json.dumps({
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Action": "sts:AssumeRole",
                        "Principal": {
                            "Service": "lambda.amazonaws.com"
                        },
                        "Effect": "Allow",
                        "Sid": ""
                    }
                ]
            })

        @pulumi.runtime.test
        def it_exists(sut):
            assert sut.lambda_role

        @pulumi.runtime.test
        def it_has_a_name(sut):
            return assert_outputs_equal(sut.lambda_role.name, f"{sut.name}-lambda-role")

        @pulumi.runtime.test
        def it_has_a_policy(sut, assume_role_policy):
            return assert_outputs_equal(sut.lambda_role.assume_role_policy, assume_role_policy)

        @pulumi.runtime.test
        def it_has_tags(sut):
            assert sut.tags == sut.tags

    def describe_a_policy_attachment():
        @pulumi.runtime.test
        def it_exists(sut):
            assert sut.execution_policy_attachment

        @pulumi.runtime.test
        def it_has_a_role(sut):
            return assert_outputs_equal(sut.execution_policy_attachment.role, sut.lambda_role.name)

        @pulumi.runtime.test
        def it_has_a_policy_arn(sut):
            return assert_outputs_equal(sut.execution_policy_attachment.policy_arn,
                                        "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole")

    def describe_a_lambda_layer():
        @pulumi.runtime.test
        def it_exists(sut):
            assert sut.lambda_layer

        @pulumi.runtime.test
        def it_has_a_name(sut):
            return assert_outputs_equal(sut.lambda_layer.layer_name, f"{sut.name}-layer")

        @pulumi.runtime.test
        def it_has_a_code_file(sut):
            filename = "../lambda.zip"
            return assert_output_equals(sut.lambda_function.code.path, pulumi.FileArchive(filename).path)

        @pulumi.runtime.test
        def it_has_a_runtime(sut, lambda_args):
            return assert_outputs_equal(sut.lambda_layer.compatible_runtimes, [lambda_args.runtime])

    def describe_a_lambda_function():
        @pytest.fixture
        def lambda_args(faker):
            return LambdaArgs(
                handler=faker.word(),
                runtime="python3.9",
                layers=[faker.word(), faker.word()],
            )

        @pulumi.runtime.test
        def it_exists(sut):
            assert sut.lambda_function

        def it_has_a_name(sut):
            return assert_outputs_equal(sut.lambda_function.name, f"{sut.name}-lambda-function")

        @pulumi.runtime.test
        def it_has_a_code_file(sut):
            filename = "../lambda.zip"
            return assert_output_equals(sut.lambda_function.code.path, pulumi.FileArchive(filename).path)

        @pulumi.runtime.test
        def it_has_a_role(sut):
            return assert_outputs_equal(sut.lambda_function.role, sut.lambda_role.arn)

        @pulumi.runtime.test
        def it_has_a_handler(sut, lambda_args):
            return assert_output_equals(sut.lambda_function.handler, lambda_args.handler)

        @pulumi.runtime.test
        def it_has_a_runtime(sut, lambda_args):
            return assert_output_equals(sut.lambda_function.runtime, lambda_args.runtime)

        @pulumi.runtime.test
        def it_has_a_timeout(sut):
            return assert_output_equals(sut.lambda_function.timeout, 60)

        @pulumi.runtime.test
        def it_has_layers(sut, lambda_args):
            expected_layers = lambda_args.layers + [sut.lambda_layer.arn]
            return assert_outputs_equal(sut.lambda_function.layers, expected_layers)

        @pulumi.runtime.test
        def it_specifies_the_memory_size(sut):
            return assert_output_equals(sut.lambda_function.memory_size, 1024)

        @pulumi.runtime.test
        def it_has_environment_variables(sut, lambda_env_variables):
            return assert_outputs_equal(sut.lambda_function.environment, {"variables": lambda_env_variables.variables})

        @pulumi.runtime.test
        def it_has_tags(sut):
            return assert_output_equals(sut.lambda_function.tags, sut.tags)
