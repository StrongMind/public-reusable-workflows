import os

import pulumi.runtime
import pulumi_aws
import pytest
from faker.contrib.pytest.plugin import faker
from pulumi import Output

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
        return f"{environment}"

    @pytest.fixture
    def pulumi_mocks(faker):
        return get_pulumi_mocks(faker)

    @pytest.fixture
    def name(faker):
        return faker.word()

    @pytest.fixture
    def component_arguments():
        return {}

    @pytest.fixture
    def sut(pulumi_set_mocks,
            component_arguments,
            name):
        import strongmind_deployment.redis

        sut = strongmind_deployment.redis.RedisComponent(name,
                                                         **component_arguments
                                                         )
        return sut

    def it_exists(sut):
        assert sut

    def describe_a_redis_cluster():
        def it_has_a_cluster(sut):
            assert sut.cluster

        def it_is_named(sut, name):
            assert sut.cluster._name == name

        @pulumi.runtime.test
        def test_it_has_a_cluster_id(sut, name, app_name, stack):
            return assert_output_equals(sut.cluster.cluster_id, f"{app_name}-{stack}-{name}")

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

        @pulumi.runtime.test
        def it_has_url(sut):
            return assert_outputs_equal(sut.url,
                                        Output.concat('redis://',
                                                      sut.cluster.cache_nodes[0].address,
                                                      ':6379'))

        def describe_with_a_alternative_namespace():
            @pytest.fixture
            def namespace(faker):
                return f'{faker.word()}-{faker.word()}-namespace'

            @pytest.fixture
            def component_arguments(component_arguments, namespace):
                component_arguments['namespace'] = namespace
                return component_arguments

            @pulumi.runtime.test
            def test_it_has_a_cluster_id(sut, name):
                return assert_output_equals(sut.cluster.cluster_id, name)

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

    def describe_a_redis_queue_cluster():
        @pytest.fixture
        def sut(component_arguments, stack):
            import strongmind_deployment.redis

            sut = strongmind_deployment.redis.QueueComponent(stack,
                                                             **component_arguments
                                                             )
            return sut

        @pulumi.runtime.test
        def it_uses_a_queue_parameter_group(sut, app_name, stack):
            return assert_output_equals(sut.cluster.parameter_group_name, f"{app_name}-{stack}-queue-redis7")

        @pulumi.runtime.test
        def it_creates_its_parameter_group(sut, app_name, stack):
            assert isinstance(sut.parameter_group, pulumi_aws.elasticache.ParameterGroup)
            return assert_output_equals(sut.parameter_group.name, f"{app_name}-{stack}-queue-redis7")

        def describe_with_a_custom_namespace():
            @pytest.fixture
            def namespace(faker):
                return f'{faker.word()}-{faker.word()}-queue'

            @pytest.fixture
            def component_arguments(component_arguments, namespace):
                component_arguments['namespace'] = namespace
                return component_arguments

            @pulumi.runtime.test
            def it_uses_a_queue_parameter_group(sut, namespace):
                return assert_output_equals(sut.cluster.parameter_group_name, f"{namespace}-queue-redis7")

            @pulumi.runtime.test
            def it_creates_its_parameter_group(sut, namespace):
                assert isinstance(sut.parameter_group, pulumi_aws.elasticache.ParameterGroup)
                return assert_output_equals(sut.parameter_group.name, f"{namespace}-queue-redis7")

        @pulumi.runtime.test
        def it_sets_the_parameter_group_family(sut):
            return assert_output_equals(sut.parameter_group.family, "redis7")

        @pulumi.runtime.test
        def it_sets_the_cache_eviction_policy_to_noeviction(sut):
            assert_output_equals(sut.parameter_group.parameters[0].name, "maxmemory-policy")
            assert_output_equals(sut.parameter_group.parameters[0].value, "noeviction")

    def describe_a_redis_cache_cluster():
        @pytest.fixture
        def sut(component_arguments, stack):
            import strongmind_deployment.redis

            sut = strongmind_deployment.redis.CacheComponent(stack,
                                                             **component_arguments
                                                             )
            return sut

        @pulumi.runtime.test
        def it_uses_a_cache_parameter_group(sut, app_name, stack):
            return assert_output_equals(sut.cluster.parameter_group_name, f"{app_name}-{stack}-cache-redis7")

        @pulumi.runtime.test
        def it_creates_its_parameter_group(sut, app_name, stack):
            assert isinstance(sut.parameter_group, pulumi_aws.elasticache.ParameterGroup)
            return assert_output_equals(sut.parameter_group.name, f"{app_name}-{stack}-cache-redis7")

        @pulumi.runtime.test
        def it_sets_the_parameter_group_family(sut):
            return assert_output_equals(sut.parameter_group.family, "redis7")

        def describe_with_a_custom_namespace():
            @pytest.fixture
            def namespace(faker):
                return f'{faker.word()}-{faker.word()}-cache'

            @pytest.fixture
            def component_arguments(component_arguments, namespace):
                component_arguments['namespace'] = namespace
                return component_arguments

            @pulumi.runtime.test
            def it_uses_a_cache_parameter_group(sut, namespace):
                return assert_output_equals(sut.cluster.parameter_group_name, f"{namespace}-cache-redis7")

            @pulumi.runtime.test
            def it_creates_its_parameter_group(sut, namespace):
                assert isinstance(sut.parameter_group, pulumi_aws.elasticache.ParameterGroup)
                return assert_output_equals(sut.parameter_group.name, f"{namespace}-cache-redis7")

        @pulumi.runtime.test
        def it_sets_the_cache_eviction_policy_to_allkeys_lru(sut):
           assert_output_equals(sut.parameter_group.parameters[0].name, "maxmemory-policy")
           assert_output_equals(sut.parameter_group.parameters[0].value, "allkeys-lru")
