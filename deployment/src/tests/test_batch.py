import os
import json

import pulumi.runtime
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
        def it_has_an_execution_role(sut):
            assert sut.execution_role

        @pulumi.runtime.test
        def it_has_a_project_stack(sut):
            assert sut.project_stack

        @pulumi.runtime.test
        def it_has_a_execution_role_with_a_name(sut):
            return assert_output_equals(sut.execution_role.name, f"{sut.project_stack}-execution-role")

        @pulumi.runtime.test
        def it_has_a_execution_role_with_a_role_policy(sut):
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
        

        @pulumi.runtime.test
        def it_has_an_execution_policy(sut):
            assert sut.execution_policy

        @pulumi.runtime.test
        def it_has_a_execution_policy_with_a_name(sut):
            return assert_output_equals(sut.execution_policy.name, f"{sut.project_stack}-execution-policy")

        @pulumi.runtime.test
        def it_has_a_execution_policy_with_a_policy(sut):
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
        def it_has_a_execution_policy_with_a_role_attached(sut):
            def check_role(role):
                def compare_roles(role_id):
                    assert role == role_id
                sut.execution_role.id.apply(compare_roles)
                return True
            
            # Check if the execution role is attached to the policy
            return sut.execution_policy.role.apply(check_role)

        @pulumi.runtime.test
        def it_has_a_compute_environment(sut):
            assert sut.create_env

        @pulumi.runtime.test
        def it_has_a_compute_environment_with_a_name(sut):
            return assert_output_equals(sut.create_env.compute_environment_name, f"{sut.project_stack}-batch")
        
        @pulumi.runtime.test
        def it_has_correct_compute_resources(sut):
            def check_compute_resources(compute_resources):
                assert compute_resources['max_vcpus'] == sut.max_vcpus
                assert compute_resources['type'] == "FARGATE"
                return True
            
            return sut.create_env.compute_resources.apply(check_compute_resources)
        
        @pulumi.runtime.test
        def it_has_a_compute_environment_with_a_service_role(sut):
            return sut.create_env.service_role.apply(lambda role: assert_outputs_equal(role, sut.execution_role.arn))

        @pulumi.runtime.test
        def it_has_a_job_queue(sut):
            assert sut.queue
            assert sut.queue is not None

        @pulumi.runtime.test
        def it_has_a_log_group(sut):
            assert sut.logGroup

        @pulumi.runtime.test
        def it_has_a_job_definition(sut):
            assert sut.definition

        @pulumi.runtime.test
        def it_has_an_event_rule(sut):
            assert sut.rule

        @pulumi.runtime.test
        def it_has_an_event_target(sut):
            assert sut.event_target