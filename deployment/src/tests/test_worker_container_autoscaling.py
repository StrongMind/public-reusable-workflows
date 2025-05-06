import pulumi
import pytest
from pytest_describe import behaves_like

from tests.shared import assert_output_equals, assert_outputs_equal
from tests.a_pulumi_containerized_app import a_pulumi_containerized_app


@behaves_like(a_pulumi_containerized_app)
def describe_worker_autoscaling():
    def describe_when_turned_on():
        @pytest.fixture
        def component_kwargs(component_kwargs):
            component_kwargs["worker_autoscale"] = True
            component_kwargs["sns_topic_arn"] = "arn:aws:sns:us-east-1:123456789012:MyTopic"
            return component_kwargs

        @pulumi.runtime.test
        def it_has_autoscaling(sut):
            assert sut.worker_autoscaling

        @pulumi.runtime.test
        def it_has_a_default_namespace(sut, app_name, stack):
            assert sut.worker_autoscaling.namespace == f"{app_name}-{stack}"

        @pulumi.runtime.test
        def it_has_an_autoscaling_target(sut):
            assert sut.worker_autoscaling.worker_autoscaling_target

        @pulumi.runtime.test
        def it_no_longer_has_a_project_stack(sut):
            assert not hasattr(sut.worker_autoscaling, "project_stack")

        @pytest.fixture
        def autoscaling_target(sut):
            return sut.worker_autoscaling.worker_autoscaling_target

        @pulumi.runtime.test
        def it_has_a_default_max_capacity(autoscaling_target):
            return assert_output_equals(autoscaling_target.max_capacity, 65)

        def describe_autoscaling_overrides():
            @pytest.fixture
            def component_kwargs(component_kwargs):
                component_kwargs["worker_max_number_of_instances"] = 10
                return component_kwargs

            @pulumi.runtime.test
            def it_has_a_new_max_capacity(autoscaling_target):
                return assert_output_equals(autoscaling_target.max_capacity, 10)

        @pulumi.runtime.test
        def it_has_a_default_min_capacity(autoscaling_target):
            return assert_output_equals(autoscaling_target.min_capacity, 1)

        @pulumi.runtime.test
        def it_has_a_default_scalable_dimension_of_desired_count(autoscaling_target):
            return assert_output_equals(autoscaling_target.scalable_dimension, "ecs:service:DesiredCount")

        @pulumi.runtime.test
        def it_uses_the_default_service_namespace_of_ecs(autoscaling_target):
            return assert_output_equals(autoscaling_target.service_namespace, "ecs")

        @pulumi.runtime.test
        def it_uses_the_clusters_resource_id(sut, autoscaling_target):
            service_id = sut.fargate_service.service.id.apply(lambda x: x.split(":")[-1])
            return assert_outputs_equal(autoscaling_target.resource_id, service_id)

        def describe_autoscaling_out_alarm():
            @pulumi.runtime.test
            def it_exists(sut):
                assert sut.worker_autoscaling.worker_autoscaling_out_alarm

            @pytest.fixture
            def autoscaling_out_alarm(sut):
                return sut.worker_autoscaling.worker_autoscaling_out_alarm

            @pulumi.runtime.test
            def it_is_named_auto_scaling_out_alarm(autoscaling_out_alarm, app_name, stack):
                return assert_output_equals(autoscaling_out_alarm.name,
                                            f"{app_name}-{stack}-worker-auto-scaling-out-alarm")

            @pulumi.runtime.test
            def it_triggers_when_greater_than_or_equal_to_threshold(autoscaling_out_alarm):
                return assert_output_equals(autoscaling_out_alarm.comparison_operator, "GreaterThanThreshold")

            @pulumi.runtime.test
            def it_evaluates_for_one_period(autoscaling_out_alarm):
                return assert_output_equals(autoscaling_out_alarm.evaluation_periods, 1)

            @pulumi.runtime.test
            def it_has_the_metric_name_of_max_queue_latency(autoscaling_out_alarm):
                return assert_output_equals(autoscaling_out_alarm.metric_name, "MaxQueueLatency")

            def describe_when_canvas_is_true():
                @pytest.fixture
                def component_kwargs(component_kwargs):
                    component_kwargs["namespace"] = "new_canvas"
                    return component_kwargs

                @pulumi.runtime.test
                def it_has_the_metric_name_of_job_staleness(autoscaling_out_alarm):
                    return assert_output_equals(autoscaling_out_alarm.metric_name, "JobStaleness")

            @pulumi.runtime.test
            def it_has_the_unit_of_seconds(autoscaling_out_alarm):
                return assert_output_equals(autoscaling_out_alarm.unit, "Seconds")

            @pulumi.runtime.test
            def it_checks_the_dimensions(autoscaling_out_alarm):
                return assert_output_equals(autoscaling_out_alarm.dimensions["QueueName"], "AllQueues")

            @pulumi.runtime.test
            def it_belongs_to_the_project_stack_namespace(sut, autoscaling_out_alarm):
                return assert_output_equals(autoscaling_out_alarm.namespace, sut.namespace)

            @pulumi.runtime.test
            def it_runs_every_minute(autoscaling_out_alarm):
                return assert_output_equals(autoscaling_out_alarm.period, 60)

            @pulumi.runtime.test
            def it_triggers_when_the_threshold_crosses_60(sut, autoscaling_out_alarm):
                return assert_output_equals(autoscaling_out_alarm.threshold, 60)

            @pulumi.runtime.test
            def it_triggers_the_autoscaling_policy(sut, autoscaling_out_alarm):
                return assert_outputs_equal(autoscaling_out_alarm.alarm_actions,
                                            [sut.worker_autoscaling.worker_autoscaling_out_policy.arn])

        def describe_worker_queue_latency_alarm():
            @pulumi.runtime.test
            def it_exists(sut):
                assert sut.worker_autoscaling.worker_queue_latency_alarm

            @pytest.fixture
            def queue_latency_alarm(sut):
                return sut.worker_autoscaling.worker_queue_latency_alarm

            @pulumi.runtime.test
            def it_is_named_worker_queue_latency_alarm(queue_latency_alarm, app_name, stack):
                return assert_output_equals(queue_latency_alarm.name, f"{app_name}-{stack}-worker-queue-latency-alarm")

            @pulumi.runtime.test
            def it_triggers_when_greater_than_or_equal_to_threshold(queue_latency_alarm):
                return assert_output_equals(queue_latency_alarm.comparison_operator, "GreaterThanThreshold")

            @pulumi.runtime.test
            def it_evaluates_for_one_period(queue_latency_alarm):
                return assert_output_equals(queue_latency_alarm.evaluation_periods, 1)

            @pulumi.runtime.test
            def it_has_the_metric_name_of_max_queue_latency(queue_latency_alarm):
                return assert_output_equals(queue_latency_alarm.metric_name, "MaxQueueLatency")

            def describe_when_canvas_is_true():
                @pytest.fixture
                def component_kwargs(component_kwargs):
                    component_kwargs["namespace"] = "new_canvas"
                    return component_kwargs

                @pulumi.runtime.test
                def it_has_the_metric_name_of_job_staleness(queue_latency_alarm):
                    return assert_output_equals(queue_latency_alarm.metric_name, "JobStaleness")

            @pulumi.runtime.test
            def it_has_the_unit_of_seconds(queue_latency_alarm):
                return assert_output_equals(queue_latency_alarm.unit, "Seconds")

            @pulumi.runtime.test
            def it_checks_the_dimensions(queue_latency_alarm):
                return assert_output_equals(queue_latency_alarm.dimensions["QueueName"], "AllQueues")

            @pulumi.runtime.test
            def it_belongs_to_the_project_stack_namespace(sut, queue_latency_alarm):
                return assert_output_equals(queue_latency_alarm.namespace, sut.namespace)

            @pulumi.runtime.test
            def it_runs_every_minute(queue_latency_alarm):
                return assert_output_equals(queue_latency_alarm.period, 60)

            @pulumi.runtime.test
            def it_triggers_when_the_threshold_crosses_44000(sut, queue_latency_alarm):
                return assert_output_equals(queue_latency_alarm.threshold, 44000)

            @pulumi.runtime.test
            def it_triggers_the_sns_topic(sut, queue_latency_alarm):
                return assert_outputs_equal(queue_latency_alarm.alarm_actions, [sut.sns_topic_arn])

            @pulumi.runtime.test
            def it_triggers_the_sns_topic_on_ok(sut, queue_latency_alarm):
                return assert_outputs_equal(queue_latency_alarm.ok_actions, [sut.sns_topic_arn])

        def describe_autoscaling_in_alarm():
            def it_exists(sut):
                assert sut.worker_autoscaling.worker_autoscaling_in_alarm

            @pytest.fixture
            def autoscaling_in_alarm(sut):
                return sut.worker_autoscaling.worker_autoscaling_in_alarm

            @pulumi.runtime.test
            def it_is_named_auto_scaling_in_alarm(autoscaling_in_alarm, app_name, stack):
                return assert_output_equals(autoscaling_in_alarm.name,
                                            f"{app_name}-{stack}-worker-auto-scaling-in-alarm")

            @pulumi.runtime.test
            def it_triggers_when_less_than_or_equal_to_threshold(autoscaling_in_alarm):
                return assert_output_equals(autoscaling_in_alarm.comparison_operator, "LessThanOrEqualToThreshold")

            @pulumi.runtime.test
            def it_evaluates_for_five_periods(autoscaling_in_alarm):
                return assert_output_equals(autoscaling_in_alarm.evaluation_periods, 5)

            @pulumi.runtime.test
            def it_has_the_metric_name_of_max_queue_latency(autoscaling_in_alarm):
                return assert_output_equals(autoscaling_in_alarm.metric_name, "MaxQueueLatency")

            def describe_when_canvas_is_true():
                @pytest.fixture
                def component_kwargs(component_kwargs):
                    component_kwargs["namespace"] = "new_canvas"
                    return component_kwargs

                @pulumi.runtime.test
                def it_has_the_metric_name_of_job_staleness(autoscaling_in_alarm):
                    return assert_output_equals(autoscaling_in_alarm.metric_name, "JobStaleness")

            @pulumi.runtime.test
            def it_has_the_unit_of_seconds(autoscaling_in_alarm):
                return assert_output_equals(autoscaling_in_alarm.unit, "Seconds")

            @pulumi.runtime.test
            def it_checks_the_dimensions(autoscaling_in_alarm):
                return assert_output_equals(autoscaling_in_alarm.dimensions["QueueName"], "AllQueues")

            @pulumi.runtime.test
            def it_belongs_to_the_project_stack_namespace(sut, autoscaling_in_alarm):
                return assert_output_equals(autoscaling_in_alarm.namespace, sut.namespace)

            @pulumi.runtime.test
            def it_runs_every_minute(autoscaling_in_alarm):
                return assert_output_equals(autoscaling_in_alarm.period, 60)

            @pulumi.runtime.test
            def it_triggers_the_autoscaling_in_policy(sut, autoscaling_in_alarm):
                return assert_outputs_equal(autoscaling_in_alarm.alarm_actions,
                                            [sut.worker_autoscaling.worker_autoscaling_in_policy.arn])

        def describe_autoscaling_in_policy():
            def it_exists(sut):
                assert sut.worker_autoscaling.worker_autoscaling_in_policy

            @pytest.fixture
            def autoscaling_in_policy(sut):
                return sut.worker_autoscaling.worker_autoscaling_in_policy

            @pulumi.runtime.test
            def it_is_named_autoscaling_in_policy(autoscaling_in_policy, app_name, stack):
                return assert_output_equals(autoscaling_in_policy.name,
                                            f"{app_name}-{stack}-worker-autoscaling-in-policy")

            @pulumi.runtime.test
            def it_has_a_step_scaling_policy_type(autoscaling_in_policy):
                return assert_output_equals(autoscaling_in_policy.policy_type, "StepScaling")

            @pulumi.runtime.test
            def it_uses_the_clusters_resource_id(sut, autoscaling_in_policy):
                service_id = sut.fargate_service.service.id.apply(lambda x: x.split(":")[-1])
                return assert_outputs_equal(autoscaling_in_policy.resource_id, service_id)

            @pulumi.runtime.test
            def it_has_a_default_scalable_dimension_of_desired_count(autoscaling_in_policy):
                return assert_output_equals(autoscaling_in_policy.scalable_dimension, "ecs:service:DesiredCount")

            @pulumi.runtime.test
            def it_has_a_default_service_namespace(autoscaling_in_policy):
                return assert_output_equals(autoscaling_in_policy.service_namespace, "ecs")

            @pulumi.runtime.test
            def it_has_a_step_scaling_policy_configuration(autoscaling_in_policy):
                assert autoscaling_in_policy.step_scaling_policy_configuration

            @pulumi.runtime.test
            def it_has_a_default_cooldown(autoscaling_in_policy):
                return assert_output_equals(autoscaling_in_policy.step_scaling_policy_configuration.cooldown, 60)

            @pulumi.runtime.test
            def it_changes_capacity(autoscaling_in_policy):
                return assert_output_equals(autoscaling_in_policy.step_scaling_policy_configuration.adjustment_type,
                                            "ChangeInCapacity")

            @pulumi.runtime.test
            def it_has_a_default_minimum_metric_aggregation_type(autoscaling_in_policy):
                return assert_output_equals(
                    autoscaling_in_policy.step_scaling_policy_configuration.metric_aggregation_type, "Maximum")

            @pulumi.runtime.test
            def it_has_steps(autoscaling_in_policy):
                assert autoscaling_in_policy.step_scaling_policy_configuration.step_adjustments

            def describe_step():
                @pytest.fixture
                def step(autoscaling_in_policy):
                    return autoscaling_in_policy.step_scaling_policy_configuration.step_adjustments[0]

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
            def it_exists(sut):
                assert sut.worker_autoscaling.worker_autoscaling_out_policy

            @pytest.fixture
            def autoscaling_out_policy(sut):
                return sut.worker_autoscaling.worker_autoscaling_out_policy

            @pulumi.runtime.test
            def it_is_named_autoscaling_out_policy(autoscaling_out_policy, app_name, stack):
                return assert_output_equals(autoscaling_out_policy.name,
                                            f"{app_name}-{stack}-worker-autoscaling-out-policy")

            @pulumi.runtime.test
            def it_has_a_step_scaling_policy_type(autoscaling_out_policy):
                return assert_output_equals(autoscaling_out_policy.policy_type, "StepScaling")

            @pulumi.runtime.test
            def it_uses_the_clusters_resource_id(sut, autoscaling_out_policy):
                service_id = sut.fargate_service.service.id.apply(lambda x: x.split(":")[-1])
                return assert_outputs_equal(autoscaling_out_policy.resource_id, service_id)

            @pulumi.runtime.test
            def it_has_a_default_scalable_dimension_of_desired_count(autoscaling_out_policy):
                return assert_output_equals(autoscaling_out_policy.scalable_dimension, "ecs:service:DesiredCount")

            @pulumi.runtime.test
            def it_has_a_default_service_namespace(autoscaling_out_policy):
                return assert_output_equals(autoscaling_out_policy.service_namespace, "ecs")

            @pulumi.runtime.test
            def it_has_a_step_scaling_policy_configuration(autoscaling_out_policy):
                assert autoscaling_out_policy.step_scaling_policy_configuration

            @pulumi.runtime.test
            def it_has_a_default_cooldown(autoscaling_out_policy):
                return assert_output_equals(autoscaling_out_policy.step_scaling_policy_configuration.cooldown, 60)

            @pulumi.runtime.test
            def it_changes_capacity(autoscaling_out_policy):
                return assert_output_equals(autoscaling_out_policy.step_scaling_policy_configuration.adjustment_type,
                                            "ChangeInCapacity")

            @pulumi.runtime.test
            def it_has_a_default_maximum_metric_aggregation_type(autoscaling_out_policy):
                return assert_output_equals(
                    autoscaling_out_policy.step_scaling_policy_configuration.metric_aggregation_type, "Maximum")

            @pulumi.runtime.test
            def it_has_steps(autoscaling_out_policy):
                assert autoscaling_out_policy.step_scaling_policy_configuration.step_adjustments

            def describe_first_step():
                @pytest.fixture
                def step(autoscaling_out_policy):
                    return autoscaling_out_policy.step_scaling_policy_configuration.step_adjustments[0]

                @pulumi.runtime.test
                def it_triggers_when_it_exceeds_the_alarm_threshold(step):
                    return assert_output_equals(step.metric_interval_lower_bound, "0")

                @pulumi.runtime.test
                def it_triggers_when_it_exceeds_the_alarm_threshold_by_up_to_ten(step):
                    return assert_output_equals(step.metric_interval_upper_bound, "600")

                @pulumi.runtime.test
                def it_scales_up_by_one_instance(step):
                    return assert_output_equals(step.scaling_adjustment, 1)

            def describe_second_step():
                @pytest.fixture
                def step(sut):
                    return \
                    sut.worker_autoscaling.worker_autoscaling_out_policy.step_scaling_policy_configuration.step_adjustments[
                        1]

                @pulumi.runtime.test
                def it_triggers_when_it_exceeds_the_alarm_threshold_by_more_than_600(step):
                    return assert_output_equals(step.metric_interval_lower_bound, "600")

                @pulumi.runtime.test
                def it_triggers_at_all_higher_values_than_600(step):
                    return assert_output_equals(step.metric_interval_upper_bound, None)

                @pulumi.runtime.test
                def It_step_scales_by_one_instance(step):
                    return assert_output_equals(step.scaling_adjustment, 1)


        def describe_when_given_a_custom_namespace():
            @pytest.fixture
            def namespace(faker):
                return faker.word() + "_namespace"

            @pytest.fixture
            def component_kwargs(component_kwargs, namespace):
                component_kwargs["namespace"] = namespace
                return component_kwargs

            @pulumi.runtime.test
            def it_uses_the_custom_namespace(sut, namespace):
                assert sut.worker_autoscaling.namespace == namespace

    def describe_when_turned_off():
        @pytest.fixture
        def component_kwargs(component_kwargs):
            component_kwargs["worker_autoscale"] = False
            return component_kwargs

        @pulumi.runtime.test
        def it_does_not_have_autoscaling(sut):
            assert not sut.worker_autoscaling