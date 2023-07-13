import os

import pulumi.runtime
import pytest

from tests.shared import assert_outputs_equal, assert_output_equals
from tests.mocks import get_pulumi_mocks


def describe_a_pulumi_redis_component():
    @pytest.fixture
    def app_name(faker):
        return faker.word()

    @pytest.fixture
    def environment(faker):
        return faker.word()

    @pytest.fixture
    def stack(faker, app_name, environment):
        return f"{app_name}-{environment}"

    @pytest.fixture
    def pulumi_mocks(faker):
        return get_pulumi_mocks(faker)

    @pytest.fixture
    def component_arguments():
        return {}

    @pytest.fixture
    def sut(pulumi_set_mocks,
            component_arguments
            ):
        import strongmind_deployment.redis

        sut = strongmind_deployment.redis.RedisComponent("redis",
                                                         **component_arguments
                                                         )
        return sut

    def it_exists(sut):
        assert sut

    def describe_a_redis_cluster():
        def it_has_a_cluster(sut):
            assert sut.cluster

        @pulumi.runtime.test
        def it_has_engine_redis(sut):
            return assert_output_equals(sut.cluster.engine, "redis")

        @pulumi.runtime.test
        def it_has_engine_version(sut):
            return assert_output_equals(sut.cluster.engine_version, "7.0")

        @pulumi.runtime.test
        def it_has_parameter_group_name(sut):
            return assert_output_equals(sut.cluster.parameter_group_name, "default.redis7")

        @pulumi.runtime.test
        def it_has_port(sut):
            return assert_output_equals(sut.cluster.port, 6379)

        def describe_with_defaults():
            @pulumi.runtime.test
            def test_it_has_node_type(sut):
                return assert_output_equals(sut.cluster.node_type, "cache.t4g.small")

            @pulumi.runtime.test
            def it_has_num_cache_nodes(sut):
                return assert_output_equals(sut.cluster.num_cache_nodes, 1)


        def describe_with_scaling_overrides():
            @pytest.fixture
            def component_arguments():
                return {
                    "node_type": "cache.t3.small",
                    "num_cache_nodes": 2,
                }

            @pulumi.runtime.test
            def it_has_node_type(sut, component_arguments):
                return assert_output_equals(sut.cluster.node_type, "cache.t3.small")

            @pulumi.runtime.test
            def it_has_num_cache_nodes(sut, component_arguments):
                return assert_output_equals(sut.cluster.num_cache_nodes, 2)
