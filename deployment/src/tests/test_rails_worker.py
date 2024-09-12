import pulumi
import pytest
from mockito import when
from pytest_describe import behaves_like

from tests.shared import assert_output_equals
from tests.test_rails import a_pulumi_rails_app

import rails


@behaves_like(a_pulumi_rails_app)
def describe_a_pulumi_rails_app():
    def describe_with_need_worker_set():
        @pytest.fixture
        def component_kwargs(component_kwargs):
            component_kwargs['need_worker'] = True
            return component_kwargs


        @pulumi.runtime.test
        def it_creates_a_worker_container_component(sut,
                                                    worker_container_cpu,
                                                    worker_container_memory):
            def check_machine_specs(args):
                container_cpu, container_memory = args
                assert container_cpu == worker_container_cpu
                assert container_memory == worker_container_memory

            return pulumi.Output.all(
                sut.worker_container.cpu,
                sut.worker_container.memory
            ).apply(check_machine_specs)

        def describe_with_sidekiq():
            @pytest.fixture
            def sidekiq_present():
                return True

            @pulumi.runtime.test
            def it_uses_sidekiq_entry_point_for_worker(sut, worker_container_entry_point):
                assert sut.worker_container.entry_point == worker_container_entry_point

            @pulumi.runtime.test
            def it_uses_sidekiq_as_a_default_cmd(sut):
                assert sut.worker_container.command == ["sh", "-c", "bundle exec sidekiq"]

        def describe_with_a_custom_cmd():
            @pytest.fixture
            def component_kwargs(component_kwargs):
                component_kwargs['worker_cmd'] = ["sh", "-c", "/usr/src/worker.sh"]
                return component_kwargs

            @pulumi.runtime.test
            def it_uses_the_custom_command(sut):
                assert sut.worker_container.command == ["sh", "-c", "/usr/src/worker.sh"]

        @pulumi.runtime.test
        def it_does_not_need_load_balancer(sut):
            assert not sut.worker_container.need_load_balancer

        @pulumi.runtime.test
        def it_uses_cluster_from_web_container(sut):
            assert sut.worker_container.ecs_cluster_arn == sut.web_container.ecs_cluster_arn

        def describe_worker_log_metric_filters():
            @pytest.fixture
            def worker_log_metric_filters(faker):
                return [
                    {
                        "pattern": "BLAH DAH",
                        "metric_transformation": {
                            "name": "waiting_workers",
                            "namespace": "Jobs",
                            "value": "$BLAH",
                        }
                    }
                ]

            @pytest.fixture
            def component_kwargs(component_kwargs, worker_log_metric_filters):
                component_kwargs['worker_log_metric_filters'] = worker_log_metric_filters
                return component_kwargs

            @pulumi.runtime.test
            def it_passes_worker_log_metric_filter_pattern_to_worker_container(sut, worker_log_metric_filters):
                return assert_output_equals(sut.worker_container.log_metric_filters[0].pattern,
                                            "BLAH DAH")

            @pulumi.runtime.test
            def it_passes_worker_log_metric_filter_value_to_worker_container(sut, worker_log_metric_filters):
                return assert_output_equals(sut.worker_container.log_metric_filters[0].metric_transformation.value,
                                            "$BLAH")
