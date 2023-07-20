import pulumi
import pytest


def describe_a_dynamo_component():
    @pytest.fixture
    def name(faker):
        return faker.word()
    @pytest.fixture
    def sut(name):
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
        def it_is_named(sut):
            assert sut.table._name == "test"
