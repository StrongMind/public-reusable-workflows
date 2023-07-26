import pulumi
import pulumi_aws as aws
import pytest

from tests.mocks import get_pulumi_mocks
from tests.shared import assert_output_equals, assert_outputs_equal


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
        return strongmind_deployment.dynamo.DynamoComponent(name, hash_key="id", attributes={"id": "N"})

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
            def hash_key(faker):
                return faker.word()

            @pytest.fixture
            def range_key(faker):
                return faker.word()

            @pytest.fixture
            def attributes(hash_key, range_key, faker):
                return {
                    hash_key: "S",
                    range_key: "N"
                }

            @pytest.fixture
            def sut(name, attributes, pulumi_set_mocks, hash_key, range_key):
                import strongmind_deployment.dynamo
                return strongmind_deployment.dynamo.DynamoComponent(name,
                                                                    attributes=attributes,
                                                                    hash_key=hash_key,
                                                                    range_key=range_key)

            @pulumi.runtime.test
            def it_creates_the_first_dynamo_attribute(sut, hash_key):
                return assert_output_equals(sut.table.attributes[0].name, hash_key)

            @pulumi.runtime.test
            def it_creates_the_first_dynamo_type(sut, ):
                return assert_output_equals(sut.table.attributes[0].type, "S")

            @pulumi.runtime.test
            def it_creates_the_second_dynamo_attribute(sut, range_key):
                return assert_output_equals(sut.table.attributes[1].name, range_key)

            @pulumi.runtime.test
            def it_creates_the_second_dynamo_type(sut, ):
                return assert_output_equals(sut.table.attributes[1].type, "N")

            @pulumi.runtime.test
            def it_protects_the_table_from_deletion(sut):
                return assert_output_equals(sut.table.deletion_protection_enabled, True)

            @pulumi.runtime.test
            def it_sets_the_read_capacity_to_1(sut):
                return assert_output_equals(sut.table.read_capacity, 1)

            @pulumi.runtime.test
            def it_sets_the_write_capacity_to_1(sut):
                return assert_output_equals(sut.table.write_capacity, 1)

            @pulumi.runtime.test
            def it_passes_hash_key_through(sut, hash_key):
                return assert_output_equals(sut.table.hash_key, hash_key)

            @pulumi.runtime.test
            def it_passes_range_key_through(sut, range_key):
                return assert_output_equals(sut.table.range_key, range_key)

            def describe_no_hash_key():
                @pulumi.runtime.test
                def it_raises_an_error(name, attributes, pulumi_set_mocks, range_key):
                    import strongmind_deployment.dynamo
                    with pytest.raises(ValueError) as e:
                        strongmind_deployment.dynamo.DynamoComponent(name,
                                                                     attributes=attributes,
                                                                     range_key=range_key)

                        assert "Missing hash_key" in str(e.value)

            def describe_no_range_key():
                @pytest.fixture
                def sut(faker):
                    import strongmind_deployment.dynamo
                    return strongmind_deployment.dynamo.DynamoComponent(faker.word(),
                                                                        attributes={"id": "N"},
                                                                        hash_key="id")

                @pulumi.runtime.test
                def it_passes_none_through(sut):
                    return assert_output_equals(sut.table.range_key, None)

    def describe_read_autoscaling_target():
        @pulumi.runtime.test
        def it_exists(sut):
            assert sut.read_autoscaling_target

        @pulumi.runtime.test
        def it_has_max_capacity_of_40000(sut):
            return assert_output_equals(sut.read_autoscaling_target.max_capacity, 40000)

        @pulumi.runtime.test
        def it_has_min_capacity_of_1(sut):
            return assert_output_equals(sut.read_autoscaling_target.min_capacity, 1)

        @pulumi.runtime.test
        def it_points_to_dynamo_table(sut, app_name, stack, name):
            return assert_output_equals(sut.read_autoscaling_target.resource_id, f"table/{app_name}-{stack}-{name}")

        @pulumi.runtime.test
        def it_has_scalable_dimension_of_dynamodb_read_capacity_utilization(sut):
            return assert_output_equals(sut.read_autoscaling_target.scalable_dimension,
                                        "dynamodb:table:ReadCapacityUnits")

        @pulumi.runtime.test
        def it_has_service_namespace_of_dynamodb(sut):
            return assert_output_equals(sut.read_autoscaling_target.service_namespace, "dynamodb")

    def describe_table_read_policy():
        @pulumi.runtime.test
        def it_exists(sut):
            assert sut.table_read_policy

        @pulumi.runtime.test
        def it_has_policy_type(sut):
            return assert_output_equals(sut.table_read_policy.policy_type, "TargetTrackingScaling")

        @pulumi.runtime.test
        def it_points_to_read_autoscaling_target(sut, app_name, stack, name):
            return assert_output_equals(sut.table_read_policy.resource_id, f"table/{app_name}-{stack}-{name}")

        @pulumi.runtime.test
        def it_has_scalable_dimension_of_dynamodb_read_capacity_utilization(sut):
            return assert_output_equals(sut.read_autoscaling_target.scalable_dimension,
                                        "dynamodb:table:ReadCapacityUnits")

        @pulumi.runtime.test
        def it_has_service_namespace_of_dynamodb(sut):
            return assert_output_equals(sut.read_autoscaling_target.service_namespace, "dynamodb")

        @pulumi.runtime.test
        def it_has_target_tracking_scaling_policy_configuration(sut):
            return assert_output_equals(sut.table_read_policy.target_tracking_scaling_policy_configuration.predefined_metric_specification.predefined_metric_type,
                                        "DynamoDBReadCapacityUtilization")

        @pulumi.runtime.test
        def it_has_target_value_of_70(sut):
            return assert_output_equals(
                sut.table_read_policy.target_tracking_scaling_policy_configuration.target_value,
                70)

    def describe_write_autoscaling_target():
        @pulumi.runtime.test
        def it_exists(sut):
            assert sut.write_autoscaling_target

        @pulumi.runtime.test
        def it_has_max_capacity_of_40000(sut):
            return assert_output_equals(sut.write_autoscaling_target.max_capacity, 40000)

        @pulumi.runtime.test
        def it_has_min_capacity_of_1(sut):
            return assert_output_equals(sut.write_autoscaling_target.min_capacity, 1)

        @pulumi.runtime.test
        def it_points_to_dynamo_table(sut, app_name, stack, name):
            return assert_output_equals(sut.write_autoscaling_target.resource_id, f"table/{app_name}-{stack}-{name}")

        @pulumi.runtime.test
        def it_has_scalable_dimension_of_dynamodb_write_capacity_utilization(sut):
            return assert_output_equals(sut.write_autoscaling_target.scalable_dimension,
                                        "dynamodb:table:WriteCapacityUnits")

        @pulumi.runtime.test
        def it_has_service_namespace_of_dynamodb(sut):
            return assert_output_equals(sut.write_autoscaling_target.service_namespace, "dynamodb")

    def describe_table_write_policy():
        @pulumi.runtime.test
        def it_exists(sut):
            assert sut.table_write_policy

        @pulumi.runtime.test
        def it_has_policy_type(sut):
            return assert_output_equals(sut.table_write_policy.policy_type, "TargetTrackingScaling")

        @pulumi.runtime.test
        def it_points_to_write_autoscaling_target(sut, app_name, stack, name):
            return assert_output_equals(sut.table_write_policy.resource_id, f"table/{app_name}-{stack}-{name}")

        @pulumi.runtime.test
        def it_has_scalable_dimension_of_dynamodb_write_capacity_utilization(sut):
            return assert_output_equals(sut.write_autoscaling_target.scalable_dimension,
                                        "dynamodb:table:WriteCapacityUnits")

        @pulumi.runtime.test
        def it_has_service_namespace_of_dynamodb(sut):
            return assert_output_equals(sut.write_autoscaling_target.service_namespace, "dynamodb")

        @pulumi.runtime.test
        def it_has_target_tracking_scaling_policy_configuration(sut):
            return assert_output_equals(sut.table_write_policy.target_tracking_scaling_policy_configuration.predefined_metric_specification.predefined_metric_type,
                                        "DynamoDBWriteCapacityUtilization")

        @pulumi.runtime.test
        def it_has_target_value_of_70(sut):
            return assert_output_equals(
                sut.table_write_policy.target_tracking_scaling_policy_configuration.target_value,
                70)