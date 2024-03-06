import pytest
import pulumi
import json
#from strongmind_deployment.cloudfront import DistributionComponent
from tests.mocks import get_pulumi_mocks

def describe_a_distribution_component():
    @pytest.fixture
    def app_name(faker):
        print(f"app_name: {app_name}")
        return faker.word()

    @pytest.fixture
    def environment(faker):
        print(f"environment: {environment}")
        return faker.word()

    @pytest.fixture
    def stack(faker, app_name, environment):
        print(f"app_name: {app_name}")
        print(f"environment: {environment}")
        return f"{app_name}-{environment}"
    
    @pytest.fixture
    def pulumi_mocks(faker):
        return get_pulumi_mocks(faker)

    @pytest.fixture
    def sut(pulumi_set_mocks,
            app_name,
            environment,
            stack):
        import strongmind_deployment.cloudfront

        sut = strongmind_deployment.cloudfront.DistributionComponent(
            f"{app_name}-{environment}-distribution",
            fqdn=f"{app_name}-{environment}.example.com",
            stack=stack,
            wait_for_deployment=True,
        )
        return sut

    @pulumi.runtime.test
    def it_exists(sut):
        assert sut

