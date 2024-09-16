import pulumi
import pytest
from pytest_describe import behaves_like

from strongmind_deployment.autoscale import WorkerAutoscaleComponent
from tests.shared import assert_output_equals
from tests.test_container import a_pulumi_containerized_app
from strongmind_deployment.worker_container import WorkerContainerComponent


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
            def it_uses_the_inst_job_metrics_to_create_the_scale_out_alarm(worker_autoscaling):
                assert_output_equals(worker_autoscaling.worker_autoscaling_out_alarm, {
                    "alarmActions": [worker_autoscaling.worker_autoscaling_out_policy.arn],
                    "metricName": "EnqueuedJobs",
                    "namespace": "AWS/ECS",
                    "period": 60,
                    "statistic": "Average",
                    "threshold": 50
                })