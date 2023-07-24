import pulumi
import pulumi_aws as aws
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
        def it_has_a_table_name(sut, name, app_name, stack):
            return assert_output_equals(sut.table.name, f"{app_name}-{stack}-{name}")

        def describe_with_attributes():
            @pytest.fixture
            def attribute_name_1(faker):
                return faker.word()

            @pytest.fixture
            def attribute_name_2(faker):
                return faker.word()

            @pytest.fixture
            def attributes(attribute_name_1, attribute_name_2, faker):
                return {
                    attribute_name_1: "S",
                    attribute_name_2: "N"
                }

            @pytest.fixture
            def sut(name, attributes, pulumi_set_mocks):
                import strongmind_deployment.dynamo
                return strongmind_deployment.dynamo.DynamoComponent(name, attributes=attributes)

            @pulumi.runtime.test
            def it_creates_the_first_dynamo_attribute(sut, attribute_name_1):
                return assert_output_equals(sut.table.attributes[0].name, attribute_name_1)

            @pulumi.runtime.test
            def it_creates_the_first_dynamo_type(sut, ):
                return assert_output_equals(sut.table.attributes[0].type, "S")

            @pulumi.runtime.test
            def it_creates_the_second_dynamo_attribute(sut, attribute_name_2):
                return assert_output_equals(sut.table.attributes[1].name, attribute_name_2)

            @pulumi.runtime.test
            def it_creates_the_second_dynamo_type(sut, ):
                return assert_output_equals(sut.table.attributes[1].type, "N")
