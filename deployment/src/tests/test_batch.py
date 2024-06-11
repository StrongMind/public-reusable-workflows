import os
import json

import pulumi.runtime
import pulumi_aws as aws
from pytest_describe import behaves_like
import pytest

from tests.shared import assert_output_equals, assert_outputs_equal
from tests.mocks import get_pulumi_mocks

def a_pulumi_batch_component():
    @pytest.fixture
    def app_name(faker):
        return faker.word()
    
    @pytest.fixture
    def stack(env_name):
        return env_name

    @pytest.fixture
    def env_name(faker):
        os.environ["ENVIRONMENT_NAME"] = faker.word()
        return os.environ["ENVIRONMENT_NAME"]
    
    @pytest.fixture
    def max_vcpus(faker):
        return faker.random_int()
    
    @pytest.fixture
    def vcpu(faker):
        return faker.random_int()
    
    @pytest.fixture
    def max_memory(faker):
        return faker.random_int()
    
    @pytest.fixture
    def memory(faker):
        return faker.random_int()
    
    @pytest.fixture
    def command(faker):
        return [f'./{faker.word()}']
    
    @pytest.fixture
    def cron():
        return "cron(0 0 * * ? *)"
    
    @pytest.fixture
    def secrets(faker):
        return [{
        "name": faker.word(),
        "valueFrom": faker.password(),
        }]
    
    @pytest.fixture
    def aws_account_id(faker):
        return faker.random_int()

    @pytest.fixture
    def container_image(aws_account_id, app_name):
        os.environ["CONTAINER_IMAGE"] = f"{aws_account_id}.dkr.ecr.us-west-2.amazonaws.com/{app_name}:latest"
        return os.environ["CONTAINER_IMAGE"]
    
    @pytest.fixture
    def pulumi_mocks(faker):
        return get_pulumi_mocks(faker)

    @pytest.fixture
    def component_kwargs(pulumi_set_mocks,
                        env_name,
                        max_vcpus,
                        vcpu,
                        max_memory,
                        memory,
                        command,
                        cron,
                        secrets,
                        container_image):
        return {
            "env_name": env_name,
            "max_vcpus": max_vcpus,
            "vcpu": vcpu,
            "max_memory": max_memory,
            "memory": memory,
            "command": command,
            "cron": cron,
            "secrets": secrets,
            "container_image": container_image
        }
    
    @pytest.fixture
    def sut(component_kwargs):
        import strongmind_deployment.batch
        return strongmind_deployment.batch.BatchComponent("batch-test",
                                                        **component_kwargs)

@behaves_like(a_pulumi_batch_component)
def describe_batch():
    def describe_a_batch_component():
        @pulumi.runtime.test
        def it_exists(sut):
            assert sut

        @pulumi.runtime.test
        def it_has_a_project_stack(sut):
            assert hasattr(sut, 'project_stack')
            assert sut.project_stack is not None
           
        def describe_execution_role():
            @pulumi.runtime.test
            def it_has_an_execution_role(sut):
                assert hasattr(sut, 'execution_role')
                assert sut.execution_role is not None

            @pulumi.runtime.test
            def it_has_a_name(sut):
                return assert_output_equals(sut.execution_role.name, f"{sut.project_stack}-execution-role")

            @pulumi.runtime.test
            def it_has_a_role_policy(sut):
                return assert_output_equals(sut.execution_role.assume_role_policy, json.dumps({
                        "Version": "2008-10-17",
                        "Statement": [
                            {
                                "Sid": "",
                                "Effect": "Allow",
                                "Principal": {
                                    "Service": [
                                        "ecs-tasks.amazonaws.com",
                                        "batch.amazonaws.com",
                                        "events.amazonaws.com"
                                ]},
                                "Action": "sts:AssumeRole",
                            }
                        ],
                    }))
            
        def describe_execution_policy():
            @pulumi.runtime.test
            def it_has_an_execution_policy(sut):
                assert hasattr(sut, 'execution_role')
                assert sut.execution_role is not None

            @pulumi.runtime.test
            def it_has_a_name(sut):
                return assert_output_equals(sut.execution_policy.name, f"{sut.project_stack}-execution-policy")

            @pulumi.runtime.test
            def it_has_a_policy(sut):
                return assert_output_equals(sut.execution_policy.policy, json.dumps({
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Action": [
                                    "ecs:*",
                                    "ecr:GetAuthorizationToken",
                                    "ecr:BatchCheckLayerAvailability",
                                    "batch:*",
                                    "events:*",
                                    "s3:*",
                                    "ecr:GetDownloadUrlForLayer",
                                    "ecr:BatchGetImage",
                                    "ecr:GetRepositoryPolicy",
                                    "ecr:DescribeRepositories",
                                    "ecr:ListImages",
                                    "ecr:DescribeImages",
                                    "ecr:InitiateLayerUpload",
                                    "ecr:UploadLayerPart",
                                    "ecr:CompleteLayerUpload",
                                    "ecr:PutImage",
                                    "logs:*",
                                    "secretsmanager:GetSecretValue",
                                    "ec2:*",
                                    "iam:GetInstanceProfile",
                                    "iam:GetRole",
                                    "iam:PassRole",
                                ],
                                "Effect": "Allow",
                                "Resource": "*",
                            }
                        ],
                    }))
            
            @pulumi.runtime.test
            def it_has_a_role_attached(sut):
                def check_role(role):
                    def compare_roles(role_id):
                        assert role == role_id
                    sut.execution_role.id.apply(compare_roles)
                    return True
            
                # Check if the execution role is attached to the policy
                return sut.execution_policy.role.apply(check_role)

        def describe_compute_environment():
            @pulumi.runtime.test
            def it_has_a_compute_environment(sut):
                assert hasattr(sut, 'create_env')
                assert sut.create_env is not None

            @pulumi.runtime.test
            def it_has_a_name(sut):
                return assert_output_equals(sut.create_env.compute_environment_name, f"{sut.project_stack}-batch")
            
            @pulumi.runtime.test
            def it_has_correct_compute_resources(sut):
                def check_compute_resources(compute_resources):
                    assert compute_resources['max_vcpus'] == sut.max_vcpus
                    assert compute_resources['type'] == "FARGATE"
                    return True
                
                return sut.create_env.compute_resources.apply(check_compute_resources)
            
            @pulumi.runtime.test
            def it_has_a_service_role(sut):
                assert_outputs_equal(sut.create_env.service_role, sut.execution_role.arn)

        def describe_job_queue():
            @pulumi.runtime.test
            def it_has_a_job_queue(sut):
                assert hasattr(sut, 'queue')
                assert sut.queue is not None

            @pulumi.runtime.test
            def it_is_an_aws_batch_job_queue(sut):
                assert isinstance(sut.queue, aws.batch.JobQueue)

        def describe_log_group():
            @pulumi.runtime.test
            def it_has_a_log_group(sut):
                assert hasattr(sut, 'logGroup')
                assert sut.logGroup is not None

            @pulumi.runtime.test
            def it_is_an_aws_cloudwatch_log_group(sut):
                assert isinstance(sut.logGroup, aws.cloudwatch.LogGroup)

            @pulumi.runtime.test
            def it_has_correct_log_group_name(sut):
                expected_name = f"/aws/batch/{sut.project_stack}-job"
                return sut.logGroup.name.apply(lambda name: name == expected_name)

            @pulumi.runtime.test
            def it_has_correct_retention_in_days(sut):
                return sut.logGroup.retention_in_days.apply(lambda retention_in_days: retention_in_days == 14)

        def describe_job_definition():
            @pulumi.runtime.test
            def it_has_a_job_definition(sut):
                assert hasattr(sut, 'definition')
                assert sut.definition is not None

            @pulumi.runtime.test
            def it_is_an_aws_batch_job_definition(sut):
                assert isinstance(sut.definition, aws.batch.JobDefinition)

            @pulumi.runtime.test
            def it_has_correct_name(sut):
                expected_name = f"{sut.project_stack}-definition"
                return sut.definition.name.apply(lambda name: name == expected_name)

            @pulumi.runtime.test
            def it_has_correct_type(sut):
                assert sut.definition.type.apply(lambda type: type == "container")

            @pulumi.runtime.test
            def it_has_correct_platform_capabilities(sut):
                expected_capabilities = ["FARGATE"]
                return sut.definition.platform_capabilities.apply(lambda capabilities: capabilities == expected_capabilities)

        def describe_event_rule():
            @pulumi.runtime.test
            def it_has_an_event_rule(sut):
                assert hasattr(sut, 'rule')
                assert sut.rule is not None

            @pulumi.runtime.test
            def it_is_an_aws_cloudwatch_event_rule(sut):
                assert isinstance(sut.rule, aws.cloudwatch.EventRule)

            @pulumi.runtime.test
            def it_has_correct_name(sut):
                expected_name = f"{sut.project_stack}-eventbridge-rule"
                return sut.rule.name.apply(lambda name: name == expected_name)

            @pulumi.runtime.test
            def it_has_correct_schedule_expression(sut, cron):
                return sut.rule.schedule_expression.apply(lambda c: c == cron)

            @pulumi.runtime.test
            def it_has_correct_state(sut):
                assert sut.rule.state.apply(lambda state: state == "ENABLED")

        def describe_event_target():
            @pulumi.runtime.test
            def it_has_an_event_target(sut):
                assert hasattr(sut, 'event_target')
                assert sut.event_target is not None

            @pulumi.runtime.test
            def it_is_an_aws_cloudwatch_event_target(sut):
                assert isinstance(sut.event_target, aws.cloudwatch.EventTarget)

            @pulumi.runtime.test
            def it_has_correct_rule_name(sut):
                return pulumi.Output.all(sut.event_target.rule, sut.rule.name).apply(
                    lambda args: args[0] == args[1]
                )

            @pulumi.runtime.test
            def it_has_correct_target_arn(sut):
                return pulumi.Output.all(sut.event_target.arn, sut.queue.arn).apply(
                    lambda args: args[0] == args[1]
                )

            @pulumi.runtime.test
            def it_has_correct_role_arn(sut):
                expected_role_arn = "arn:aws:iam::221871915463:role/ecsEventsRole"
                return sut.event_target.role_arn.apply(lambda role_arn: role_arn == expected_role_arn)

            @pulumi.runtime.test
            def it_has_correct_batch_target(sut):
                def check_batch_target(batch_target):
                    return pulumi.Output.all(
                        batch_target['job_definition'], sut.definition.arn,
                        batch_target['job_name'], sut.rule.name,
                        batch_target['job_attempts']
                    ).apply(lambda args: (
                        args[0] == args[1] and
                        args[2] == args[3] and
                        args[4] == 1
                    ))

                return sut.event_target.batch_target.apply(check_batch_target)