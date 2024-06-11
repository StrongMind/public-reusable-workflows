import os

import pulumi.runtime
from pytest_describe import behaves_like
import pytest

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
        def it_has_an_execution_policy(sut):
            assert sut.execution_policy

        @pulumi.runtime.test
        def it_has_a_compute_environment(sut):
            assert sut.create_env

        @pulumi.runtime.test
        def it_has_a_job_queue(sut):
            assert sut.queue

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