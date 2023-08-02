import pulumi.runtime
import pytest

from tests.mocks import get_pulumi_mocks
from tests.shared import assert_output_equals


def describe_a_pulumi_storage_component():
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
        import strongmind_deployment.storage

        sut = strongmind_deployment.storage.StorageComponent(name,
                                                         **component_arguments
                                                         )
        return sut

    def it_exists(sut):
        assert sut

    def describe_a_storage_bucket():
        def it_has_a_bucket(sut):
            assert sut.bucket

        @pulumi.runtime.test
        def it_has_a_bucket_name(sut, app_name, stack):
            return assert_output_equals(sut.bucket.bucket, f"{app_name}-{stack}-courseware")

        @pulumi.runtime.test
        def it_has_a_bucket_acl(sut):
            return assert_output_equals(sut.bucket.acl, "private")

        @pulumi.runtime.test
        def it_has_tags(sut, app_name):
            return assert_output_equals(sut.bucket.tags, {
                "product": app_name,
                "repository": app_name,
                "service": app_name,
                "environment": sut.env_name,
            })
