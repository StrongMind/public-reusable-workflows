import random

import pulumi
import pytest
from pytest_describe import behaves_like

from tests.shared import assert_output_equals, assert_outputs_equal
from tests.a_pulumi_containerized_app import a_pulumi_containerized_app


@behaves_like(a_pulumi_containerized_app)
def describe_autoscaling():
    def describe_when_turned_on():
        @pytest.fixture
        def component_kwargs(component_kwargs):
            component_kwargs["autoscale"] = True
            return component_kwargs

        @pulumi.runtime.test
        def it_has_an_autoscaling_target(sut):
            assert sut.autoscaling_target

        @pulumi.runtime.test
        def it_has_a_default_max_capacity(sut):
            return assert_output_equals(sut.autoscaling_target.max_capacity, 100)

        def describe_autoscaling_overrides():
            @pytest.fixture
            def component_kwargs(component_kwargs):
                component_kwargs["max_number_of_instances"] = 10
                return component_kwargs

        @pulumi.runtime.test
        def it_has_a_default_min_capacity(sut):
            return assert_output_equals(sut.autoscaling_target.min_capacity, 2)

        @pulumi.runtime.test
        def it_has_a_default_scalable_dimension_of_desired_count(sut):
            return assert_output_equals(sut.autoscaling_target.scalable_dimension, "ecs:service:DesiredCount")

        @pulumi.runtime.test
        def it_uses_the_default_service_namespace_of_ecs(sut):
            return assert_output_equals(sut.autoscaling_target.service_namespace, "ecs")

        @pulumi.runtime.test
        def it_uses_the_clusters_resource_id(sut):
            service_id = sut.fargate_service.service.id.apply(lambda x: x.split(":")[-1])
            return assert_outputs_equal(sut.autoscaling_target.resource_id, service_id)

        def describe_running_tasks_alarm():
            @pulumi.runtime.test
            def it_exits(sut):
                assert sut.running_tasks_alarm

            @pulumi.runtime.test
            def it_is_named_running_tasks_alarm(sut, app_name, stack):
                return assert_output_equals(sut.running_tasks_alarm.name, f"{app_name}-{stack}-running-tasks-alarm")

            @pulumi.runtime.test
            def it_triggers_when_greater_than_threshold(sut):
                return assert_output_equals(sut.running_tasks_alarm.comparison_operator, "GreaterThanOrEqualToThreshold")

            @pulumi.runtime.test
            def it_evaluates_for_one_period(sut):
                return assert_output_equals(sut.running_tasks_alarm.evaluation_periods, 1)

            @pulumi.runtime.test
            def it_belongs_to_the_container_insights_namespace(sut):
                return assert_output_equals(sut.running_tasks_alarm.namespace, "ECS/ContainerInsights")

            @pulumi.runtime.test
            def it_runs_every_minute(sut):
                return assert_output_equals(sut.running_tasks_alarm.period, 60)

            @pulumi.runtime.test
            def it_triggers_when_the_threshold_is_more_than_the_desired_count(sut):
                expected_threshold = 100
                actual_threshold = sut.running_tasks_alarm.threshold
                assert_output_equals(actual_threshold, expected_threshold)

        def describe_autoscaling_out_alarm():
            @pulumi.runtime.test
            def it_exists(sut):
                assert sut.autoscaling_out_alarm

            @pulumi.runtime.test
            def it_is_named_auto_scaling_out_alarm(sut, app_name, stack):
                return assert_output_equals(sut.autoscaling_out_alarm.name,
                                            f"{app_name}-{stack}-auto-scaling-out-alarm")

            @pulumi.runtime.test
            def it_triggers_when_greater_than_or_equal_to_threshold(sut):
                return assert_output_equals(sut.autoscaling_out_alarm.comparison_operator,
                                            "GreaterThanOrEqualToThreshold")

            @pulumi.runtime.test
            def it_triggers_the_autoscaling_policy(sut):
                return assert_outputs_equal(sut.autoscaling_out_alarm.alarm_actions, [sut.autoscaling_out_policy.arn])

            @pulumi.runtime.test
            def it_triggers_based_on_the_response_time(sut):
                return assert_output_equals(sut.autoscaling_out_alarm.metric_name,
                                            "TargetResponseTime")

            @pulumi.runtime.test
            def it_belongs_to_the_AWS_namespace(sut):
                return assert_output_equals(sut.autoscaling_out_alarm.namespace,
                                            "AWS/ApplicationELB")

            @pulumi.runtime.test
            def it_checks_the_unit_as_a_p99(sut):
                return assert_output_equals(sut.autoscaling_out_alarm.extended_statistic, "p99")

            @pulumi.runtime.test
            def it_pulls_the_metric_data_from_the_target_group(sut):
                def check_target_group_dimension(args):
                    target_group_arn, dimensions_target_group = args
                    target_group_arn = target_group_arn.split(":")[-1]
                    assert target_group_arn == dimensions_target_group

                return pulumi.Output.all(sut.target_group.arn,
                                         sut.autoscaling_out_alarm.dimensions['TargetGroup']).apply(
                    check_target_group_dimension)

            @pulumi.runtime.test
            def it_pulls_the_metric_data_from_the_loadbalancer(sut):
                def check_loadbalancer_dimension(args):
                    loadbalancer_arn, dimensions_loadbalancer = args
                    loadbalancer_arn = loadbalancer_arn.split("/", 1)[1]
                    assert loadbalancer_arn == dimensions_loadbalancer

                return pulumi.Output.all(sut.load_balancer.arn,
                                         sut.autoscaling_out_alarm.dimensions['LoadBalancer']).apply(
                    check_loadbalancer_dimension)

            @pulumi.runtime.test
            def it_runs_every_minute(sut):
                return assert_output_equals(sut.autoscaling_out_alarm.period, 60)

            @pulumi.runtime.test
            def it_evaluates_for_one_period(sut):
                return assert_output_equals(sut.autoscaling_out_alarm.evaluation_periods, 1)

            @pulumi.runtime.test
            def it_triggers_when_the_threshold_crosses_5(sut):
                return assert_output_equals(sut.autoscaling_out_alarm.threshold, 5)

            def describe_when_using_a_custom_threshold():
                @pytest.fixture
                def autoscale_threshold():
                    return random.randint(6, 15)

                @pytest.fixture
                def component_kwargs(component_kwargs, autoscale_threshold):
                    component_kwargs["autoscale_threshold"] = autoscale_threshold
                    return component_kwargs

                @pulumi.runtime.test
                def it_triggers_when_the_threshold_crosses_the_custom_value(sut, autoscale_threshold):
                    return assert_output_equals(sut.autoscaling_out_alarm.threshold, autoscale_threshold)


            @pulumi.runtime.test
            def it_treats_missing_data_as_missing(sut):
                return assert_output_equals(sut.autoscaling_out_alarm.treat_missing_data, "missing")

            @pulumi.runtime.test
            def it_has_tags(sut):
                assert sut.autoscaling_out_alarm.tags

        def describe_autoscaling_in_alarm():
            @pulumi.runtime.test
            def it_exists(sut):
                assert sut.autoscaling_in_alarm

            @pulumi.runtime.test
            def it_is_named_auto_scaling_in_alarm(sut, app_name, stack):
                return assert_output_equals(sut.autoscaling_in_alarm.name,
                                            f"{app_name}-{stack}-auto-scaling-in-alarm")

            @pulumi.runtime.test
            def it_triggers_when_greater_than_or_equal_to_threshold(sut):
                return assert_output_equals(sut.autoscaling_in_alarm.comparison_operator,
                                            "LessThanThreshold")

            @pulumi.runtime.test
            def it_triggers_the_autoscaling_policy(sut):
                return assert_outputs_equal(sut.autoscaling_in_alarm.alarm_actions, [sut.autoscaling_in_policy.arn])

            @pulumi.runtime.test
            def it_triggers_based_on_the_response_time(sut):
                return assert_output_equals(sut.autoscaling_in_alarm.metric_name,
                                            "TargetResponseTime")

            @pulumi.runtime.test
            def it_belongs_to_the_AWS_namespace(sut):
                return assert_output_equals(sut.autoscaling_in_alarm.namespace,
                                            "AWS/ApplicationELB")

            @pulumi.runtime.test
            def it_checks_the_unit_as_a_p99(sut):
                return assert_output_equals(sut.autoscaling_in_alarm.extended_statistic, "p99")

            @pulumi.runtime.test
            def it_pulls_the_metric_data_from_the_target_group(sut):
                def check_target_group_dimension(args):
                    target_group_arn, dimensions_target_group = args
                    target_group_arn = target_group_arn.split(":")[-1]
                    assert target_group_arn == dimensions_target_group

                return pulumi.Output.all(sut.target_group.arn,
                                         sut.autoscaling_in_alarm.dimensions['TargetGroup']).apply(
                    check_target_group_dimension)

            @pulumi.runtime.test
            def it_pulls_the_metric_data_from_the_loadbalancer(sut):
                def check_loadbalancer_dimension(args):
                    loadbalancer_arn, dimensions_loadbalancer = args
                    loadbalancer_arn = loadbalancer_arn.split("/", 1)[1]
                    assert loadbalancer_arn == dimensions_loadbalancer

                return pulumi.Output.all(sut.load_balancer.arn,
                                         sut.autoscaling_in_alarm.dimensions['LoadBalancer']).apply(
                    check_loadbalancer_dimension)

            @pulumi.runtime.test
            def it_runs_every_minute(sut):
                return assert_output_equals(sut.autoscaling_in_alarm.period, 60)

            @pulumi.runtime.test
            def it_evaluates_for_5_periods(sut):
                return assert_output_equals(sut.autoscaling_in_alarm.evaluation_periods, 5)

            @pulumi.runtime.test
            def it_triggers_when_the_threshold_crosses_5(sut):
                return assert_output_equals(sut.autoscaling_in_alarm.threshold, 5)

            def describe_when_using_a_custom_threshold():
                @pytest.fixture
                def autoscale_threshold():
                    return random.randint(6, 15)

                @pytest.fixture
                def component_kwargs(component_kwargs, autoscale_threshold):
                    component_kwargs["autoscale_threshold"] = autoscale_threshold
                    return component_kwargs

                @pulumi.runtime.test
                def it_triggers_when_the_threshold_crosses_the_custom_value(sut, autoscale_threshold):
                    return assert_output_equals(sut.autoscaling_in_alarm.threshold, autoscale_threshold)

            @pulumi.runtime.test
            def it_treats_missing_data_as_missing(sut):
                return assert_output_equals(sut.autoscaling_in_alarm.treat_missing_data, "missing")

            @pulumi.runtime.test
            def it_has_tags(sut):
                assert sut.autoscaling_in_alarm.tags

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
                resource_id = f"service/{sut.namespace}/{sut.namespace}"
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
                return assert_output_equals(sut.autoscaling_in_policy.step_scaling_policy_configuration.cooldown, 300)

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
                def it_scales_down_by_one_instance(step):
                    return assert_output_equals(step.scaling_adjustment, -1)

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
                resource_id = f"service/{sut.namespace}/{sut.namespace}"
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
                return assert_output_equals(sut.autoscaling_out_policy.step_scaling_policy_configuration.cooldown, 15)

            @pulumi.runtime.test
            def it_changes_capacity(sut):
                return assert_output_equals(
                    sut.autoscaling_out_policy.step_scaling_policy_configuration.adjustment_type,
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
