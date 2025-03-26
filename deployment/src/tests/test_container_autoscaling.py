import random
import re
import os

import pulumi
import pytest
from pytest_describe import behaves_like

from strongmind_deployment.container import ContainerComponent
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
            def it_triggers_when_greater_than_or_equal_to_threshold(sut):
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
            def it_checks_the_unit_as_a_p95(sut):
                return assert_output_equals(sut.autoscaling_out_alarm.extended_statistic, "p95")

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
            def it_checks_the_unit_as_a_p95(sut):
                return assert_output_equals(sut.autoscaling_in_alarm.extended_statistic, "p95")

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

    def describe_scheduled_scaling():
        def describe_when_enabled():
            @pytest.fixture
            def component_kwargs(component_kwargs):
                os.environ['ENVIRONMENT_NAME'] = 'prod'
                component_kwargs["autoscale"] = True
                component_kwargs["scheduled_scaling"] = True
                component_kwargs["pre_scale_time"] = "06:00"
                component_kwargs["post_scale_time"] = "18:00"
                component_kwargs["peak_min_capacity"] = 3
                return component_kwargs

            @pulumi.runtime.test
            def it_creates_scale_up_action(sut):
                assert sut.peak_scale_up

            @pulumi.runtime.test
            def it_names_scale_up_action_correctly(sut):
                return assert_output_equals(
                    sut.peak_scale_up.name,
                    f"{sut.namespace}-pre-scale-action"
                )

            @pulumi.runtime.test
            def it_uses_correct_scale_up_cron_expression(sut):
                return assert_output_equals(
                    sut.peak_scale_up.schedule,
                    "cron(0 00 06 ? * MON-FRI)"
                )

            @pulumi.runtime.test
            def it_uses_mst_timezone(sut):
                return assert_output_equals(
                    sut.peak_scale_up.timezone,
                    "Etc/GMT+7"
                )

            @pulumi.runtime.test
            def it_sets_correct_peak_min_capacity(sut):
                return assert_output_equals(
                    sut.peak_scale_up.scalable_target_action.min_capacity,
                    3
                )

            @pulumi.runtime.test
            def it_preserves_max_capacity(sut):
                return assert_output_equals(
                    sut.peak_scale_up.scalable_target_action.max_capacity,
                    100
                )

            @pulumi.runtime.test
            def it_uses_ecs_service_namespace(sut):
                return assert_output_equals(
                    sut.peak_scale_up.service_namespace,
                    "ecs"
                )

            @pulumi.runtime.test
            def it_uses_desired_count_scalable_dimension(sut):
                return assert_output_equals(
                    sut.peak_scale_up.scalable_dimension,
                    "ecs:service:DesiredCount"
                )

            @pulumi.runtime.test
            def it_uses_the_clusters_resource_id(sut):
                return assert_outputs_equal(
                    sut.peak_scale_up.resource_id,
                    sut.autoscaling_target.resource_id
                )

            @pulumi.runtime.test
            def it_depends_on_autoscaling_target(sut):
                # Verify dependency through resource properties
                return pulumi.Output.all(
                    sut.peak_scale_up.service_namespace,
                    sut.peak_scale_up.resource_id,
                    sut.peak_scale_up.scalable_dimension,
                    sut.autoscaling_target.service_namespace,
                    sut.autoscaling_target.resource_id,
                    sut.autoscaling_target.scalable_dimension
                ).apply(lambda args: all([
                    args[0] == args[3],  # service_namespace matches
                    args[1] == args[4],  # resource_id matches
                    args[2] == args[5]   # scalable_dimension matches
                ]))

            def describe_with_different_times():
                @pytest.fixture
                def component_kwargs(component_kwargs):
                    component_kwargs["autoscale"] = True
                    component_kwargs["scheduled_scaling"] = True
                    component_kwargs["pre_scale_time"] = "23:00"
                    component_kwargs["post_scale_time"] = "23:59"
                    component_kwargs["peak_min_capacity"] = 3
                    return component_kwargs

                @pulumi.runtime.test
                def it_handles_end_of_day_time(sut):
                    return assert_output_equals(
                        sut.peak_scale_up.schedule,
                        "cron(0 00 23 ? * MON-FRI)"
                    )

            @pulumi.runtime.test
            def it_creates_scale_down_action(sut):
                assert sut.peak_scale_down

            @pulumi.runtime.test
            def it_names_scale_down_action_correctly(sut):
                return assert_output_equals(
                    sut.peak_scale_down.name,
                    f"{sut.namespace}-post-scale-action"
                )

            @pulumi.runtime.test
            def it_uses_correct_scale_down_cron_expression(sut):
                return assert_output_equals(
                    sut.peak_scale_down.schedule,
                    "cron(0 00 18 ? * MON-FRI)"
                )

            @pulumi.runtime.test
            def it_uses_mst_timezone_for_scale_down(sut):
                return assert_output_equals(
                    sut.peak_scale_down.timezone,
                    "Etc/GMT+7"
                )

            @pulumi.runtime.test
            def it_sets_correct_off_peak_min_capacity(sut):
                return assert_output_equals(
                    sut.peak_scale_down.scalable_target_action.min_capacity,
                    2  # default min_capacity
                )

            @pulumi.runtime.test
            def it_preserves_max_capacity_for_scale_down(sut):
                return assert_output_equals(
                    sut.peak_scale_down.scalable_target_action.max_capacity,
                    100
                )

            @pulumi.runtime.test
            def it_uses_ecs_service_namespace_for_scale_down(sut):
                return assert_output_equals(
                    sut.peak_scale_down.service_namespace,
                    "ecs"
                )

            @pulumi.runtime.test
            def it_uses_desired_count_scalable_dimension_for_scale_down(sut):
                return assert_output_equals(
                    sut.peak_scale_down.scalable_dimension,
                    "ecs:service:DesiredCount"
                )

            @pulumi.runtime.test
            def it_uses_the_clusters_resource_id_for_scale_down(sut):
                return assert_outputs_equal(
                    sut.peak_scale_down.resource_id,
                    sut.autoscaling_target.resource_id
                )

            @pulumi.runtime.test
            def it_depends_on_scale_up_and_autoscaling_target(sut):
                # Verify dependency through resource properties
                return pulumi.Output.all(
                    sut.peak_scale_down.service_namespace,
                    sut.peak_scale_down.resource_id,
                    sut.peak_scale_down.scalable_dimension,
                    sut.autoscaling_target.service_namespace,
                    sut.autoscaling_target.resource_id,
                    sut.autoscaling_target.scalable_dimension
                ).apply(lambda args: all([
                    args[0] == args[3],  # service_namespace matches
                    args[1] == args[4],  # resource_id matches
                    args[2] == args[5]   # scalable_dimension matches
                ]))

            def describe_with_different_times():
                @pytest.fixture
                def component_kwargs(component_kwargs):
                    component_kwargs["autoscale"] = True
                    component_kwargs["scheduled_scaling"] = True
                    component_kwargs["pre_scale_time"] = "23:00"
                    component_kwargs["post_scale_time"] = "23:59"
                    component_kwargs["peak_min_capacity"] = 3
                    return component_kwargs

                @pulumi.runtime.test
                def it_handles_end_of_day_time(sut):
                    return assert_output_equals(
                        sut.peak_scale_down.schedule,
                        "cron(0 59 23 ? * MON-FRI)"
                    )

        def describe_when_disabled():
            @pytest.fixture
            def component_kwargs(component_kwargs):
                component_kwargs["autoscale"] = True
                component_kwargs["scheduled_scaling"] = False
                return component_kwargs

            @pulumi.runtime.test
            def it_does_not_create_scheduled_action(sut):
                assert not hasattr(sut, 'peak_scale_up')


@behaves_like(a_pulumi_containerized_app)
def describe_container_validation():
    def describe_scheduled_scaling_validation():
        def describe_time_format():
            @pytest.fixture
            def base_kwargs():
                return {
                    "autoscale": True,
                    "scheduled_scaling": True,
                    "peak_min_capacity": 3
                }

            def it_rejects_invalid_pre_scale_time(base_kwargs):
                base_kwargs["pre_scale_time"] = "25:00"
                base_kwargs["post_scale_time"] = "12:00"
                with pytest.raises(ValueError, match=re.escape("pre_scale_time must be in 'HH:MM' format (24-hour)")):
                    ContainerComponent("test", None, **base_kwargs)

            def it_rejects_invalid_post_scale_time(base_kwargs):
                base_kwargs["pre_scale_time"] = "09:00"
                base_kwargs["post_scale_time"] = "25:00"
                with pytest.raises(ValueError, match=re.escape("pre_scale_time must be in 'HH:MM' format (24-hour)")):
                    ContainerComponent("test", None, **base_kwargs)

            def it_rejects_invalid_time_window(base_kwargs):
                base_kwargs["pre_scale_time"] = "09:00"
                base_kwargs["post_scale_time"] = "08:00"
                with pytest.raises(ValueError, match=re.escape("post_scale_time must be after pre_scale_time")):
                    ContainerComponent("test", None, **base_kwargs)

        def describe_required_parameters():
            def it_requires_all_parameters():
                kwargs = {
                    "autoscale": True,
                    "scheduled_scaling": True
                }
                with pytest.raises(ValueError, match=re.escape("pre_scale_time, post_scale_time, and peak_min_capacity must be provided when scheduled_scaling is enabled")):
                    ContainerComponent("test", None, **kwargs)
