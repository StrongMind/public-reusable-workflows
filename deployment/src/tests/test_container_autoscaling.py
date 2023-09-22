import pulumi
import pytest
from pytest_describe import behaves_like

from tests.shared import assert_output_equals, assert_outputs_equal
from tests.test_container import a_pulumi_containerized_app


@behaves_like(a_pulumi_containerized_app)
def describe_autoscaling():
    def describe_when_turned_on():
        @pytest.fixture
        def component_kwargs(component_kwargs):
            component_kwargs["autoscaling"] = True
            return component_kwargs
        @pulumi.runtime.test
        def it_has_an_autoscaling_target(sut):
            assert sut.autoscaling_target

        @pulumi.runtime.test
        def it_has_a_default_max_capacity(sut):
            return assert_output_equals(sut.autoscaling_target.max_capacity, 1)

        def describe_autoscaling_overrides():
            @pytest.fixture
            def component_kwargs(component_kwargs):
                component_kwargs["max_number_of_instances"] = 10
                return component_kwargs

            @pulumi.runtime.test
            def it_has_a_configurable_max_capacity(sut):
                return assert_output_equals(sut.autoscaling_target.max_capacity, 10)

        @pulumi.runtime.test
        def it_has_a_default_min_capacity(sut):
            return assert_output_equals(sut.autoscaling_target.min_capacity, 1)

        @pulumi.runtime.test
        def it_has_a_default_scalable_dimension_of_desired_count(sut):
            return assert_output_equals(sut.autoscaling_target.scalable_dimension, "ecs:service:DesiredCount")

        @pulumi.runtime.test
        def it_uses_the_default_service_namespace_of_ecs(sut):
            return assert_output_equals(sut.autoscaling_target.service_namespace, "ecs")

        @pulumi.runtime.test
        def it_uses_the_clusters_resource_id(sut):
            resource_id = f"service/{sut.project_stack}/{sut.project_stack}"
            return assert_output_equals(sut.autoscaling_target.resource_id, resource_id)

        def describe_autoscaling_out_alarm():
            @pulumi.runtime.test
            def it_exists(sut):
                assert sut.autoscaling_out_alarm

            @pulumi.runtime.test
            def it_is_named_auto_scaling_out_alarm(sut, app_name, stack):
                return assert_output_equals(sut.autoscaling_out_alarm.name, f"{app_name}-{stack}-auto-scaling-out-alarm")

            @pulumi.runtime.test
            def it_triggers_when_greater_than_or_equal_to_threshold(sut):
                return assert_output_equals(sut.autoscaling_out_alarm.comparison_operator, "GreaterThanOrEqualToThreshold")

            @pulumi.runtime.test
            def it_evaluates_for_one_period(sut):
                return assert_output_equals(sut.autoscaling_out_alarm.evaluation_periods, 1)

            @pulumi.runtime.test
            def it_triggers_based_on_CPU_utilization(sut):
                return assert_output_equals(sut.autoscaling_out_alarm.metric_name, "CPUUtilization")

            @pulumi.runtime.test
            def it_checks_the_unit_as_a_percentage(sut):
                return assert_output_equals(sut.autoscaling_out_alarm.unit, "Percent")

            @pulumi.runtime.test
            def it_pulls_the_metric_data_from_the_cluster(sut):
                return assert_output_equals(sut.autoscaling_out_alarm.dimensions["ClusterName"], sut.project_stack)

            @pulumi.runtime.test
            def it_pulls_the_metric_data_from_the_service(sut):
                return assert_output_equals(sut.autoscaling_out_alarm.dimensions["ServiceName"], sut.project_stack)

            @pulumi.runtime.test
            def it_belongs_to_the_ECS_namespace(sut):
                return assert_output_equals(sut.autoscaling_out_alarm.namespace, "AWS/ECS")

            @pulumi.runtime.test
            def it_runs_every_minute(sut):
                return assert_output_equals(sut.autoscaling_out_alarm.period, 60)

            @pulumi.runtime.test
            def it_uses_average_statistic_by_default(sut):
                return assert_output_equals(sut.autoscaling_out_alarm.statistic, "Average")

            @pulumi.runtime.test
            def it_triggers_when_CPU_utilization_is_over_65(sut):
                return assert_output_equals(sut.autoscaling_out_alarm.threshold, 65)

            @pulumi.runtime.test
            def it_triggers_the_autoscaling_policy(sut):
                return assert_outputs_equal(sut.autoscaling_out_alarm.alarm_actions, [sut.autoscaling_out_policy.arn])

        def describe_autoscaling_in_alarm():
            def it_exists(sut):
                assert sut.autoscaling_in_alarm

            @pulumi.runtime.test
            def it_is_named_auto_scaling_in_alarm(sut, app_name, stack):
                return assert_output_equals(sut.autoscaling_in_alarm.name,
                                            f"{app_name}-{stack}-auto-scaling-in-alarm")

            @pulumi.runtime.test
            def it_triggers_when_less_than_or_equal_to_threshold(sut):
                return assert_output_equals(sut.autoscaling_in_alarm.comparison_operator, "LessThanOrEqualToThreshold")

            @pulumi.runtime.test
            def it_evaluates_for_five_periods(sut):
                return assert_output_equals(sut.autoscaling_in_alarm.evaluation_periods, 5)

            @pulumi.runtime.test
            def it_triggers_based_on_CPU_utilization(sut):
                return assert_output_equals(sut.autoscaling_in_alarm.metric_name, "CPUUtilization")

            @pulumi.runtime.test
            def it_checks_the_unit_as_a_percentage(sut):
                return assert_output_equals(sut.autoscaling_in_alarm.unit, "Percent")

            @pulumi.runtime.test
            def it_pulls_the_metric_data_from_the_cluster(sut):
                return assert_output_equals(sut.autoscaling_in_alarm.dimensions["ClusterName"], sut.project_stack)

            @pulumi.runtime.test
            def it_pulls_the_metric_data_from_the_service(sut):
                return assert_output_equals(sut.autoscaling_in_alarm.dimensions["ServiceName"], sut.project_stack)

            @pulumi.runtime.test
            def it_belongs_to_the_ECS_namespace(sut):
                return assert_output_equals(sut.autoscaling_in_alarm.namespace, "AWS/ECS")

            @pulumi.runtime.test
            def it_runs_every_minute(sut):
                return assert_output_equals(sut.autoscaling_in_alarm.period, 60)

            @pulumi.runtime.test
            def it_uses_average_statistic_by_default(sut):
                return assert_output_equals(sut.autoscaling_in_alarm.statistic, "Average")

            @pulumi.runtime.test
            def it_triggers_when_CPU_utilization_is_under_50(sut):
                return assert_output_equals(sut.autoscaling_in_alarm.threshold, 50)

        def describe_autoscaling_in_policy():
            def it_exists(sut):
                assert sut.autoscaling_in_policy

            @pulumi.runtime.test
            def it_is_named_autoscaling_in_policy(sut, app_name, stack):
                return assert_output_equals(sut.autoscaling_in_policy.name, f"{app_name}-{stack}-autoscaling-in-policy")

            @pulumi.runtime.test
            def it_has_a_step_scaling_policy_type(sut):
                return assert_output_equals(sut.autoscaling_in_policy.policy_type, "StepScaling")

            @pulumi.runtime.test
            def it_uses_the_clusters_resource_id(sut):
                resource_id = f"service/{sut.project_stack}/{sut.project_stack}"
                return assert_output_equals(sut.autoscaling_in_policy.resource_id, resource_id)

            @pulumi.runtime.test
            def it_has_a_default_scalable_dimension_of_desired_count(sut):
                return assert_output_equals(sut.autoscaling_in_policy.scalable_dimension, "ecs:service:DesiredCount")

            @pulumi.runtime.test
            def it_has_a_default_service_namespace(sut):
                return assert_output_equals(sut.autoscaling_in_policy.service_namespace, "ecs")

            @pulumi.runtime.test
            def it_has_a_step_scaling_policy_configuration(sut):
                assert sut.autoscaling_in_policy.step_scaling_policy_configuration

            @pulumi.runtime.test
            def it_has_a_default_cooldown(sut):
                return assert_output_equals(sut.autoscaling_in_policy.step_scaling_policy_configuration.cooldown, 60)

            @pulumi.runtime.test
            def it_changes_capacity(sut):
                return assert_output_equals(sut.autoscaling_in_policy.step_scaling_policy_configuration.adjustment_type,
                                            "ChangeInCapacity")

            @pulumi.runtime.test
            def it_has_a_default_minimum_metric_aggregation_type(sut):
                return assert_output_equals(
                    sut.autoscaling_in_policy.step_scaling_policy_configuration.metric_aggregation_type, "Maximum")

            @pulumi.runtime.test
            def it_has_steps(sut):
                assert sut.autoscaling_in_policy.step_scaling_policy_configuration.step_adjustments

            def describe_step():
                @pytest.fixture
                def step(sut):
                    return sut.autoscaling_in_policy.step_scaling_policy_configuration.step_adjustments[0]

                @pulumi.runtime.test
                def it_has_no_lower_bound(step):
                    return assert_output_equals(step.metric_interval_lower_bound, None)

                @pulumi.runtime.test
                def it_triggers_when_it_is_below_the_alarm_threshold(step):
                    return assert_output_equals(step.metric_interval_upper_bound, "0")

                @pulumi.runtime.test
                def it_scales_up_by_one_instance(step):
                    return assert_output_equals(step.scaling_adjustment, 1)

        def describe_autoscaling_out_policy():
            @pulumi.runtime.test
            def it_exists(sut):
                assert sut.autoscaling_out_policy

            @pulumi.runtime.test
            def it_is_named_autoscaling_out_policy(sut, app_name, stack):
                return assert_output_equals(sut.autoscaling_out_policy.name,
                                            f"{app_name}-{stack}-autoscaling-out-policy")

            @pulumi.runtime.test
            def it_has_a_step_scaling_policy_type(sut):
                return assert_output_equals(sut.autoscaling_out_policy.policy_type, "StepScaling")

            @pulumi.runtime.test
            def it_uses_the_clusters_resource_id(sut):
                resource_id = f"service/{sut.project_stack}/{sut.project_stack}"
                return assert_output_equals(sut.autoscaling_out_policy.resource_id, resource_id)

            @pulumi.runtime.test
            def it_has_a_default_scalable_dimension_of_desired_count(sut):
                return assert_output_equals(sut.autoscaling_out_policy.scalable_dimension, "ecs:service:DesiredCount")

            @pulumi.runtime.test
            def it_has_a_default_service_namespace(sut):
                return assert_output_equals(sut.autoscaling_out_policy.service_namespace, "ecs")

            @pulumi.runtime.test
            def it_has_a_step_scaling_policy_configuration(sut):
                assert sut.autoscaling_out_policy.step_scaling_policy_configuration

            @pulumi.runtime.test
            def it_has_a_default_cooldown(sut):
                return assert_output_equals(sut.autoscaling_out_policy.step_scaling_policy_configuration.cooldown, 60)

            @pulumi.runtime.test
            def it_changes_capacity(sut):
                return assert_output_equals(sut.autoscaling_out_policy.step_scaling_policy_configuration.adjustment_type,
                                            "ChangeInCapacity")

            @pulumi.runtime.test
            def it_has_a_default_maximum_metric_aggregation_type(sut):
                return assert_output_equals(
                    sut.autoscaling_out_policy.step_scaling_policy_configuration.metric_aggregation_type, "Maximum")

            @pulumi.runtime.test
            def it_has_steps(sut):
                assert sut.autoscaling_out_policy.step_scaling_policy_configuration.step_adjustments

            def describe_first_step():
                @pytest.fixture
                def step(sut):
                    return sut.autoscaling_out_policy.step_scaling_policy_configuration.step_adjustments[0]

                @pulumi.runtime.test
                def it_triggers_when_it_exceeds_the_alarm_threshold(step):
                    return assert_output_equals(step.metric_interval_lower_bound, "0")

                @pulumi.runtime.test
                def it_triggers_when_it_exceeds_the_alarm_threshold_by_up_to_ten(step):
                    return assert_output_equals(step.metric_interval_upper_bound, "10")

                @pulumi.runtime.test
                def it_scales_up_by_one_instance(step):
                    return assert_output_equals(step.scaling_adjustment, 1)

            def describe_second_step():
                @pytest.fixture
                def step(sut):
                    return sut.autoscaling_out_policy.step_scaling_policy_configuration.step_adjustments[1]

                @pulumi.runtime.test
                def it_triggers_when_it_exceeds_the_alarm_threshold_by_more_than_ten(step):
                    return assert_output_equals(step.metric_interval_lower_bound, "10")

                @pulumi.runtime.test
                def it_triggers_at_all_higher_values_than_ten(step):
                    return assert_output_equals(step.metric_interval_upper_bound, None)

                @pulumi.runtime.test
                def it_scales_up_by_three_instances(step):
                    return assert_output_equals(step.scaling_adjustment, 3)
