import os

import pytest
from tests.mocks import get_pulumi_mocks


def a_pulumi_containerized_app():
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
    def entry_point(faker):
        return f'./{faker.word()}'

    @pytest.fixture
    def command(faker):
        return f'./{faker.word()}'

    @pytest.fixture
    def aws_account_id(faker):
        return faker.random_int()

    @pytest.fixture
    def container_image(aws_account_id, app_name):
        return f"{aws_account_id}.dkr.ecr.us-west-2.amazonaws.com/{app_name}:latest"

    @pytest.fixture
    def env_vars(faker, environment):
        return {
            "ENVIRONMENT_NAME": environment,
        }

    @pytest.fixture
    def secrets(faker):
        return [{
            faker.word(): faker.password(),
        }]

    @pytest.fixture
    def zone_id(faker):
        return faker.word()

    @pytest.fixture
    def load_balancer_dns_name(faker):
        return f"{faker.word()}.{faker.word()}.{faker.word()}"

    @pytest.fixture
    def resource_record_name(faker):
        return f"{faker.word()}.{faker.word()}.{faker.word()}"

    @pytest.fixture
    def resource_record_value(faker):
        return f"{faker.word()}.{faker.word()}.{faker.word()}"

    @pytest.fixture
    def resource_record_type(faker):
        return faker.word()

    @pytest.fixture
    def domain_validation_options(faker, resource_record_name, resource_record_value, resource_record_type):
        class FakeValidationOption:
            def __init__(self, name, value, type):
                self.resource_record_name = name
                self.resource_record_value = value
                self.resource_record_type = type

            pass

        return [FakeValidationOption(resource_record_name, resource_record_value, resource_record_type)]

    @pytest.fixture
    def need_load_balancer():
        return True

    @pytest.fixture
    def component_kwargs(pulumi_set_mocks,
                         app_name,
                         app_path,
                         container_port,
                         cpu,
                         memory,
                         entry_point,
                         command,
                         container_image,
                         env_vars,
                         secrets,
                         zone_id,
                         load_balancer_dns_name,
                         domain_validation_options,
                         ):
        return {
            "app_path": app_path,
            "container_port": container_port,
            "cpu": cpu,
            "memory": memory,
            "entry_point": entry_point,
            "command": command,
            "container_image": container_image,
            "env_vars": env_vars,
            "secrets": secrets,
            "zone_id": zone_id,
            "load_balancer_dns_name": load_balancer_dns_name,
            "domain_validation_options": domain_validation_options
        }

    @pytest.fixture
    def sut(component_kwargs):
        import strongmind_deployment.container
        return strongmind_deployment.container.ContainerComponent("container",
                                                                  **component_kwargs
                                                                  )

    def it_exists(sut):
        assert sut
