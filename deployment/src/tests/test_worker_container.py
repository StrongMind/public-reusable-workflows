import pulumi
import pytest
from pulumi import Output
from pytest_describe import behaves_like

from strongmind_deployment import worker_container
from strongmind_deployment.worker_autoscale import WorkerAutoscaleComponent
from tests.shared import assert_output_equals
from tests.test_container import a_pulumi_containerized_app
from strongmind_deployment.worker_container import WorkerContainerComponent


def assert_outputs_equal_array(expected_output, actual_output):
    def compare(args):
        expected, actual = args
        try:
            assert expected == [actual]
        except AssertionError:
            print(f"Expected: {expected}")
            print(f"Actual: {actual}")
            raise

    return Output.all(expected_output, actual_output).apply(compare)


@behaves_like(a_pulumi_containerized_app)
def describe_a_worker_container():
    @pytest.fixture
    def sut(component_kwargs):
        return WorkerContainerComponent("worker", **component_kwargs)

    @pytest.fixture
    def inst_jobs_present():
        return False

    @pytest.fixture(autouse=True)
    def inst_jobs_present_mock(when, inst_jobs_present):
        when(worker_container).inst_jobs_present().thenReturn(inst_jobs_present)

    def describe_with_inst_jobs_present():
        @pytest.fixture
        def inst_jobs_present():
            return True

        @pulumi.runtime.test
        def it_uses_the_worker_script_provided(sut):
            assert sut.command == ["sh", "-c", "/usr/src/worker.sh"]

        def describe_a_worker_autoscale_component():
            @pytest.fixture
            def worker_autoscaling(sut):
                return sut.worker_autoscaling

            @pulumi.runtime.test
            def it_creates_a_worker_autoscale_component(worker_autoscaling):
                assert worker_autoscaling is not None
                assert isinstance(worker_autoscaling, WorkerAutoscaleComponent)

            @pulumi.runtime.test
            def it_sets_the_out_alarm_actions(worker_autoscaling):
                return assert_outputs_equal_array(worker_autoscaling.worker_autoscaling_out_alarm.alarm_actions,
                                                  worker_autoscaling.worker_autoscaling_out_policy.arn)

            @pulumi.runtime.test
            def it_sets_the_out_alarm_metric_name(worker_autoscaling):
                return assert_output_equals(worker_autoscaling.worker_autoscaling_out_alarm.metric_name, "JobStaleness")

            @pulumi.runtime.test
            def it_sets_the_out_alarm_namespace(sut, worker_autoscaling):
                return assert_output_equals(worker_autoscaling.worker_autoscaling_out_alarm.namespace, "Canvas")

            @pulumi.runtime.test
            def it_sets_the_dimenions(worker_autoscaling, stack, app_name):
                return assert_output_equals(worker_autoscaling.worker_autoscaling_out_alarm.dimensions, {"domain": f"{stack}-{app_name}.strongmind.com"})

            @pulumi.runtime.test
            def it_sets_the_out_alarm_period(worker_autoscaling):
                return assert_output_equals(worker_autoscaling.worker_autoscaling_out_alarm.period, 60)

            @pulumi.runtime.test
            def it_sets_the_out_alarm_statistic(worker_autoscaling):
                return assert_output_equals(worker_autoscaling.worker_autoscaling_out_alarm.statistic, "Maximum")

            @pulumi.runtime.test
            def it_sets_the_out_alarm_threshold(worker_autoscaling):
                return assert_output_equals(worker_autoscaling.worker_autoscaling_out_alarm.threshold, 60)
