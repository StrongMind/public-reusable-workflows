import os

import pulumi.runtime
import pytest
import pulumi_aws as aws

from strongmind_deployment.container import ContainerComponent
from tests.mocks import get_pulumi_mocks


def describe_a_dashboard_component():
    @pytest.fixture
    def name(faker):
        return faker.word()

    @pytest.fixture
    def app_name(faker):
        return faker.word()

    @pytest.fixture
    def environment(faker):
        os.environ["ENVIRONMENT_NAME"] = faker.word()
        return os.environ["ENVIRONMENT_NAME"]

    @pytest.fixture
    def stack(environment):
        return environment

    @pytest.fixture
    def pulumi_mocks(faker):
        return get_pulumi_mocks(faker)

    @pytest.fixture
    def domain_validation_options(faker):
        class FakeValidationOption:
            def __init__(self):
                self.resource_record_name = faker.word()
                self.resource_record_value = faker.word()
                self.resource_record_type = faker.word()

        return [FakeValidationOption()]

    @pytest.fixture
    def web_container_component_kwargs(pulumi_set_mocks, domain_validation_options):
        return {
            "app_path": "/",
            "container_port": '80',
            "cpu": "1",
            "memory": "128",
            "entry_point": "/entry_point",
            "command": "command",
            "container_image": "image",
            "env_vars": {},
            "secrets": {},
            "zone_id": "something",
            "load_balancer_dns_name": "something.strongmind.com",
            "domain_validation_options": domain_validation_options
        }

    @pytest.fixture
    def web_container(name, web_container_component_kwargs):
        return ContainerComponent(name, **web_container_component_kwargs)

    @pytest.fixture
    def ecs_cluster(pulumi_set_mocks):
        return aws.ecs.Cluster("cluster",
                           tags={},
                           settings=[{
                               "name": "containerInsights",
                               "value": "enabled",
                           }],
                           opts=pulumi.ResourceOptions(),
                           )

    @pytest.fixture
    def rds_serverless_cluster_instance(pulumi_set_mocks):
        return aws.rds.ClusterInstance("rds-cluster-instance",
                                       cluster_identifier="rds-cluster",
                                       instance_class="db.t3.micro",
                                       engine="aurora-postgresql",
                                       publicly_accessible=True,
                                       opts=pulumi.ResourceOptions(),
                                       )
    @pytest.fixture
    def sut(name, web_container, ecs_cluster, rds_serverless_cluster_instance, pulumi_set_mocks):
        from strongmind_deployment.dashboard import DashboardComponent
        return DashboardComponent(name,
                                  project_stack='project-stack',
                                  web_container=web_container,
                                  ecs_cluster=ecs_cluster,
                                  rds_serverless_cluster_instance=rds_serverless_cluster_instance)

    @pulumi.runtime.test
    def it_exists(sut):
        assert True

    @pulumi.runtime.test
    def it_has_a_default_namespace_based_on_project_stack(sut, app_name, stack):
        assert sut.namespace == f"{app_name}-{stack}"

    @pulumi.runtime.test
    def it_no_longer_has_a_project_stack(sut):
        assert not hasattr(sut, 'project_stack')

    def describe_with_a_custom_namespace():
        @pytest.fixture
        def namespace(faker):
            return faker.word()

        @pytest.fixture
        def sut(name, web_container, ecs_cluster, rds_serverless_cluster_instance, namespace, pulumi_set_mocks):
            from strongmind_deployment.dashboard import DashboardComponent
            return DashboardComponent(name,
                                      project_stack='project-stack',
                                      web_container=web_container,
                                      ecs_cluster=ecs_cluster,
                                      rds_serverless_cluster_instance=rds_serverless_cluster_instance,
                                      namespace=namespace)

        @pulumi.runtime.test
        def it_has_a_custom_namespace(sut, namespace):
            assert sut.namespace == namespace