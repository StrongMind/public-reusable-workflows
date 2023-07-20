import pulumi
import pytest

from tests.mocks import get_pulumi_mocks
from tests.shared import assert_output_equals


def describe_a_dynamo_component():
    @pytest.fixture
    def environment(faker):
        return faker.word()

    @pytest.fixture
    def stack(faker, app_name, environment):
        return f"{environment}"

    @pytest.fixture
    def name(faker):
        return faker.word()

    @pytest.fixture
    def app_name(faker):
        return faker.word()

    @pytest.fixture
    def pulumi_mocks(faker):
        return get_pulumi_mocks(faker)

    @pytest.fixture
    def sut(name, pulumi_set_mocks):
        import strongmind_deployment.dynamo
        return strongmind_deployment.dynamo.DynamoComponent(name)

    @pulumi.runtime.test
    def it_exists(sut):
        assert sut

    @pulumi.runtime.test
    def it_is_a_component_resource(sut):
        assert isinstance(sut, pulumi.ComponentResource)

    def describe_a_table():
        @pulumi.runtime.test
        def it_exists(sut):
            assert sut.table

        @pulumi.runtime.test
        def it_is_named(sut, name):
            assert sut.table._name == name

        @pulumi.runtime.test
        def it_registers_with_pulumi_with_its_type_string(sut):
            assert sut._type == "strongmind:global_build:commons:dynamo"

        @pulumi.runtime.test
        def test_it_has_a_table_name(sut, name, app_name, stack):
            return assert_output_equals(sut.table.name, f"{app_name}-{stack}-{name}")

