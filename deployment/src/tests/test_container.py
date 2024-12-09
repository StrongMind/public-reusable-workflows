import json
import os

import pulumi.runtime
import pytest
from pytest_describe import behaves_like

from tests.a_pulumi_containerized_app import a_pulumi_containerized_app
from tests.shared import assert_output_equals, assert_outputs_equal


@behaves_like(a_pulumi_containerized_app)
def describe_container():
    def describe_a_container_component():
        def describe_with_no_memory_or_cpu_passed_to_kwargs():
            @pytest.fixture
            def component_kwargs(component_kwargs):
                component_kwargs.pop('memory')
                component_kwargs.pop('cpu')
                return component_kwargs

            @pulumi.runtime.test
            def it_defaults_cpu_and_memory(sut):
                def check_task_definition(args):
                    task_definition_dict = args[0]
                    container = task_definition_dict["container"]
                    assert container["memory"] == 4096
                    assert container["cpu"] == 2048

                return pulumi.Output.all(sut.fargate_service.task_definition_args).apply(check_task_definition)

        @pulumi.runtime.test
        def it_creates_an_ecs_cluster(sut):
            assert sut.ecs_cluster

        @pulumi.runtime.test
        def it_sets_the_cluster_name(sut, stack, app_name):
            def check_cluster_name(args):
                cluster_name = args[0]
                assert cluster_name == f"{app_name}-{stack}"

            return pulumi.Output.all(sut.ecs_cluster.name).apply(check_cluster_name)

        @pulumi.runtime.test
        def it_has_environment_variables(sut, app_name, env_vars):
            assert sut.env_vars == env_vars

        @pulumi.runtime.test
        def it_has_an_execution_role(sut):
            assert sut.execution_role

        @pulumi.runtime.test
        def it_has_a_task_role_named(sut, stack, app_name):
            return assert_output_equals(sut.task_role.name, f"{app_name}-{stack}-task-role")

        @pulumi.runtime.test
        def it_has_an_execution_role_named(sut, stack, app_name):
            return assert_output_equals(sut.execution_role.name, f"{app_name}-{stack}-execution-role")

        @pulumi.runtime.test
        def it_has_a_task_role_with_access_to_ecs(sut):
            return assert_output_equals(sut.task_role.assume_role_policy, json.dumps({
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "",
                        "Effect": "Allow",
                        "Principal": {
                            "Service": "ecs-tasks.amazonaws.com"
                        },
                        "Action": "sts:AssumeRole"
                    }
                ]
            }))

        @pulumi.runtime.test
        def it_has_a_task_policy_named(sut, stack, app_name):
            return assert_output_equals(sut.task_policy.name, f"{app_name}-{stack}-task-policy")

        @pulumi.runtime.test
        def it_has_task_policy_attached_to_task_role(sut):
            return assert_outputs_equal(sut.task_policy.role, sut.task_role.id)

        @pulumi.runtime.test
        def it_has_execution_policy_attached_to_execution_role(sut):
            return assert_outputs_equal(sut.execution_policy.role, sut.execution_role.id)

        @pulumi.runtime.test
        def it_has_an_execution_policy_named(sut, stack, app_name):
            return assert_output_equals(sut.execution_policy.name, f"{app_name}-{stack}-execution-policy")

        @pulumi.runtime.test
        def it_has_a_task_policy_with_ssmmessages_access(sut):
            return assert_output_equals(sut.task_policy.policy, json.dumps({
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Action": [
                                "bedrock:InvokeModel",
                                "bedrock:InvokeModelWithResponseStream",
                                "ecs:UpdateTaskProtection",
                                "ssmmessages:CreateControlChannel",
                                "ssmmessages:CreateDataChannel",
                                "ssmmessages:OpenControlChannel",
                                "ssmmessages:OpenDataChannel",
                                "cloudwatch:*",
                                "logs:CreateLogStream",
                                "logs:PutLogEvents",
                                "s3:GetObject",
                                "s3:PutObject*",
                                "s3:DeleteObject",
                            ],
                            "Effect": "Allow",
                            "Resource": "*",
                        }
                    ],
                }))

        @pulumi.runtime.test
        def it_creates_an_s3_policy(sut):

            @pulumi.runtime.test
            def it_has_an_s3_policy_named(sut, stack, app_name):
                return assert_output_equals(sut.s3_policy.name, f"{app_name}-{stack}-s3-policy")

            @pulumi.runtime.test
            def it_has_an_s3_policy_with_storage_access(sut):
                return assert_output_equals(sut.s3_policy.policy, json.dumps({
                    "Version": "2012-10-17",
                    "Statement": [{
                        "Effect": "Allow",
                        "Action": [
                            "s3:GetObject",
                            "s3:PutObject",
                            "s3:DeleteObject"
                        ],
                        "Resource": "*"
                    }]
                }),
                tags=tags
                )

            @pulumi.runtime.test
            def test_s3_policy_attachment():
                def check_s3_policy_attachment(args):
                    sut, expected_role, expected_policy_arn = args
                    assert_output_equals(sut.s3_policy_attachment.role, expected_role)
                    assert_output_equals(sut.s3_policy_attachment.policy_arn, expected_policy_arn)

                return pulumi.Output.all(sut, sut.task_role.id, sut.s3_policy.arn).apply(check_s3_policy_attachment)

        @pulumi.runtime.test
        def it_enables_enable_execute_command(sut):
            return assert_output_equals(sut.fargate_service.enable_execute_command, True)

        @pulumi.runtime.test
        def its_execution_role_has_an_arn(sut):
            return assert_output_equals(sut.execution_role.arn,
                                        "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy")

        @pulumi.runtime.test
        def it_has_no_autoscaling_target(sut):
            assert not sut.autoscaling_target

        def describe_with_no_load_balancer():
            @pytest.fixture
            def sut(component_kwargs):
                component_kwargs["need_load_balancer"] = False
                import strongmind_deployment.container
                return strongmind_deployment.container.ContainerComponent("container",
                                                                          **component_kwargs
                                                                          )

            @pulumi.runtime.test
            def test_it_does_not_create_a_load_balancer(sut):
                assert not sut.load_balancer

            @pulumi.runtime.test
            def it_has_no_grace_period(sut):
                return assert_output_equals(sut.fargate_service.health_check_grace_period_seconds, None)

        def describe_load_balancer():
            @pulumi.runtime.test
            def it_creates_a_load_balancer(sut):
                assert sut.load_balancer

            @pulumi.runtime.test
            def it_sets_the_load_balancer_name(sut, stack, app_name):
                assert sut.load_balancer._name == f"{app_name}-{stack}"

            @pulumi.runtime.test
            def it_sets_the_access_log_bucket(sut, stack, app_name):
                expected = {
                    "bucket": "loadbalancer-logs-None",
                    "enabled": True,
                    "prefix": f"{app_name}-{stack}",
                }

                def compare(value):
                    try:
                        assert str(value) == str(expected)
                    except AssertionError:
                        print(f"Expected: {expected}")
                        print(f"Actual: {value}")
                        raise

                return sut.load_balancer.access_logs.apply(compare)

            def describe_target_group():
                @pulumi.runtime.test
                def it_sets_the_target_group_port(sut, container_port):
                    return assert_output_equals(sut.target_group.port, container_port)

                @pulumi.runtime.test
                def it_sets_the_target_group_target_type(sut):
                    return assert_output_equals(sut.target_group.target_type, "ip")

                @pulumi.runtime.test
                def it_sets_the_target_group_health_check_enabled(sut):
                    return assert_output_equals(sut.target_group.health_check.enabled, True)

                @pulumi.runtime.test
                def it_sets_the_target_group_health_check_healthy_threshold(sut):
                    return assert_output_equals(sut.target_group.health_check.healthy_threshold, 2)

                @pulumi.runtime.test
                def it_sets_the_target_group_health_check_unhealthy_threshold(sut):
                    return assert_output_equals(sut.target_group.health_check.unhealthy_threshold, 2)

                @pulumi.runtime.test
                def it_sets_the_target_group_health_check_interval(sut):
                    return assert_output_equals(sut.target_group.health_check.interval, 30)

                @pulumi.runtime.test
                def it_sets_the_target_group_health_check_matcher_to_200(sut):
                    return assert_output_equals(sut.target_group.health_check.matcher, "200")

                @pulumi.runtime.test
                def it_sets_the_target_group_health_check_path_to_up(sut):
                    return assert_output_equals(sut.target_group.health_check.path, "/up")

                @pulumi.runtime.test
                def it_sets_the_target_group_health_check_protocol(sut):
                    return assert_output_equals(sut.target_group.health_check.protocol, "HTTP")

                @pulumi.runtime.test
                def it_sets_the_target_group_health_check_timeout(sut):
                    return assert_output_equals(sut.target_group.health_check.timeout, 5)

            def describe_the_load_balancer_listener_for_https():
                @pytest.fixture
                def listener(sut):
                    return sut.load_balancer_listener

                @pytest.fixture
                def listener_rule(sut):
                    return sut.listener_rule

                @pulumi.runtime.test
                def it_has_load_balancer_listener_for_https(listener):
                    assert listener

                @pulumi.runtime.test
                def it_sets_the_load_balancer_arn(listener, sut):
                    return assert_outputs_equal(listener.load_balancer_arn, sut.load_balancer.arn)

                @pulumi.runtime.test
                def it_sets_the_certificate_arn(listener, sut):
                    return assert_outputs_equal(listener.certificate_arn, sut.cert.arn)

                @pulumi.runtime.test
                def it_sets_the_port(listener):
                    return assert_output_equals(listener.port, 443)

                @pulumi.runtime.test
                def it_sets_the_protocol(listener):
                    return assert_output_equals(listener.protocol, "HTTPS")

                @pulumi.runtime.test
                def it_has_a_listener_rule_connected_to_the_listener(listener_rule, listener):
                    return assert_outputs_equal(listener_rule.listener_arn, listener.arn)

                @pulumi.runtime.test
                def it_forwards_to_the_target_group_with_a_rule(listener_rule, sut):
                    return assert_outputs_equal(listener_rule.actions[0].target_group_arn, sut.target_group.arn)

                @pulumi.runtime.test
                def it_forwards(listener_rule):
                    return assert_output_equals(listener_rule.actions[0].type, "forward")

                @pulumi.runtime.test
                def it_defaults_to_fixed_response(listener):
                    return assert_output_equals(listener.default_actions[0].type, "fixed-response")

                @pulumi.runtime.test
                def it_defaults_to_404(listener):
                    return assert_output_equals(listener.default_actions[0].fixed_response.status_code, "404")

                @pulumi.runtime.test
                def it_defaults_to_text_plain(listener):
                    return assert_output_equals(listener.default_actions[0].fixed_response.content_type, "text/plain")

                @pulumi.runtime.test
                def it_defaults_to_path_not_found(listener):
                    return assert_output_equals(listener.default_actions[0].fixed_response.message_body, "Path Not Found")

            def describe_the_load_balancer_listener_for_http():
                @pytest.fixture
                def listener(sut):
                    return sut.load_balancer_listener_redirect_http_to_https

                @pulumi.runtime.test
                def it_has_load_balancer_listener_for_http(listener):
                    assert listener

                @pulumi.runtime.test
                def it_sets_the_load_balancer_arn(listener, sut):
                    return assert_outputs_equal(listener.load_balancer_arn, sut.load_balancer.arn)

                @pulumi.runtime.test
                def it_sets_the_port(listener):
                    return assert_output_equals(listener.port, 80)

                @pulumi.runtime.test
                def it_sets_the_protocol(listener):
                    return assert_output_equals(listener.protocol, "HTTP")

                @pytest.fixture
                def redirect_action(listener):
                    return listener.default_actions[0]

                @pulumi.runtime.test
                def it_redirects_to_443(redirect_action):
                    return assert_output_equals(redirect_action.redirect.port, "443")

                @pulumi.runtime.test
                def it_redirects_to_https(redirect_action):
                    return assert_output_equals(redirect_action.redirect.protocol, "HTTPS")

                @pulumi.runtime.test
                def it_redirects_with_301(redirect_action):
                    return assert_output_equals(redirect_action.redirect.status_code, "HTTP_301")

                @pulumi.runtime.test
                def it_redirects(redirect_action):
                    return assert_output_equals(redirect_action.type, "redirect")

            def describe_security_group_rules():
                @pytest.fixture
                def tls_ingress(sut):
                    return sut.alb.tls_ingress

                @pytest.fixture
                def http_ingress(sut):
                    return sut.alb.http_ingress

                @pulumi.runtime.test
                def it_allows_tls_ingress_from_anywhere(tls_ingress):
                    return assert_output_equals(tls_ingress.cidr_blocks, ["0.0.0.0/0"])

                @pulumi.runtime.test
                def it_allows_tls_ingress_on_port_443(tls_ingress):
                    return assert_output_equals(tls_ingress.from_port, 443)

                @pulumi.runtime.test
                def it_allows_http_ingress_from_anywhere(http_ingress):
                    return assert_output_equals(http_ingress.cidr_blocks, ["0.0.0.0/0"])

                @pulumi.runtime.test
                def it_allows_http_ingress_on_port_80(http_ingress):
                    return assert_output_equals(http_ingress.from_port, 80)

                @pulumi.runtime.test
                def it_allows_tls_ingress_from_sg(tls_ingress, sut):
                    return assert_outputs_equal(tls_ingress.security_group_id, sut.alb.security_group.id)

                @pulumi.runtime.test
                def it_allows_http_ingress_from_sg(http_ingress, sut):
                    return assert_outputs_equal(http_ingress.security_group_id, sut.alb.security_group.id)

                @pulumi.runtime.test
                def it_uses_tcp_for_tls_ingress(tls_ingress):
                    return assert_output_equals(tls_ingress.protocol, "tcp")

                @pulumi.runtime.test
                def it_uses_tcp_for_http_ingress(http_ingress):
                    return assert_output_equals(http_ingress.protocol, "tcp")

                @pulumi.runtime.test
                def it_uses_ingress_type_for_tls_ingress(tls_ingress):
                    return assert_output_equals(tls_ingress.type, "ingress")

                @pulumi.runtime.test
                def it_uses_ingress_type_for_http_ingress(http_ingress):
                    return assert_output_equals(http_ingress.type, "ingress")


        @pulumi.runtime.test
        def describe_the_fargate_service():
            @pulumi.runtime.test
            def it_creates_a_fargate_service(sut):
                assert sut.fargate_service

            @pulumi.runtime.test
            def it_propagate_tags(sut):
                return assert_output_equals(sut.fargate_service.propagate_tags, "SERVICE")

            @pulumi.runtime.test
            def it_has_a_ten_minute_grace_period(sut):
                return assert_output_equals(sut.fargate_service.health_check_grace_period_seconds, 600)

            @pulumi.runtime.test
            def it_has_the_cluster(sut):
                # arn is None at design time so this test doesn't really work
                def check_cluster(args):
                    service_cluster, cluster = args
                    assert service_cluster == cluster

                return pulumi.Output.all(sut.fargate_service.cluster,
                                         sut.ecs_cluster.arn).apply(check_cluster)

            @pulumi.runtime.test
            def it_has_task_definition(sut, container_port, cpu, memory, entry_point, command, stack, app_name,
                                       secrets):
                def check_task_definition(args):
                    task_definition_dict = args[0]
                    container = task_definition_dict["container"]
                    assert container["cpu"] == cpu
                    assert container["memory"] == memory
                    assert container["essential"]
                    assert container["secrets"] == secrets
                    assert container["entryPoint"] == entry_point
                    assert container["command"] == command
                    assert container["portMappings"][0]["containerPort"] == container_port
                    assert container["portMappings"][0]["hostPort"] == container_port
                    assert container["logConfiguration"]["logDriver"] == "awslogs"
                    assert container["logConfiguration"]["options"]["awslogs-group"] == f"/aws/ecs/{app_name}-{stack}"
                    assert container["logConfiguration"]["options"]["awslogs-region"] == "us-west-2"
                    assert container["logConfiguration"]["options"]["awslogs-stream-prefix"] == "container"

                return pulumi.Output.all(sut.fargate_service.task_definition_args).apply(check_task_definition)

            @pulumi.runtime.test
            def it_sends_env_vars_to_the_task_definition(sut, env_vars):
                def check_env_vars(args):
                    task_definition_dict = args[0]
                    env_var_key_value_pair_array = []
                    for var in env_vars:
                        env_var_key_value_pair_array.append({
                            "name": var,
                            "value": env_vars[var]
                        })
                    assert task_definition_dict["container"]["environment"] == env_var_key_value_pair_array

                return pulumi.Output.all(sut.fargate_service.task_definition_args).apply(check_env_vars)

            @pulumi.runtime.test
            def it_sets_the_image(sut, container_image):
                def check_image_tag(args):
                    task_definition_container_image = args[0]
                    assert task_definition_container_image == container_image

                return pulumi.Output.all(sut.fargate_service.task_definition_args["container"]["image"]).apply(
                    check_image_tag)

            @pulumi.runtime.test
            def it_sets_the_execution_role(sut):
                return assert_outputs_equal(sut.fargate_service.task_definition_args["executionRole"]["roleArn"], sut.execution_role.arn)

            @pulumi.runtime.test
            def it_sets_the_task_role(sut):
                return assert_outputs_equal(sut.fargate_service.task_definition_args["taskRole"]["roleArn"], sut.task_role.arn)

            @pulumi.runtime.test
            def it_sets_the_deployment_maximum_percent_to_200(sut):
                return assert_output_equals(sut.fargate_service.deployment_maximum_percent, 200)

        def describe_with_custom_health_check_path():
            @pytest.fixture
            def custom_health_check_path(faker):
                return f"/{faker.word()}"

            @pytest.fixture
            def component_kwargs(component_kwargs, custom_health_check_path):
                component_kwargs["custom_health_check_path"] = custom_health_check_path
                return component_kwargs

            @pulumi.runtime.test
            def it_sets_the_target_group_health_check_path(sut, custom_health_check_path):
                return assert_output_equals(sut.target_group.health_check.path, custom_health_check_path)

    def describe_dns():
        @pulumi.runtime.test
        def it_has_cname_record(sut):
            assert sut.cname_record

        @pulumi.runtime.test
        def it_has_name_with_environment_prefix(sut, stack, app_name):
            return assert_output_equals(sut.cname_record.name, f"{stack}-{app_name}")

        def describe_in_production():
            @pytest.fixture
            def environment():
                os.environ["ENVIRONMENT_NAME"] = "prod"
                return "prod"

            @pulumi.runtime.test
            def it_has_name_without_prefix(sut, app_name):
                return assert_output_equals(sut.cname_record.name, app_name)

        @pulumi.runtime.test
        def it_has_cname_type(sut):
            return assert_output_equals(sut.cname_record.type, "CNAME")

        @pulumi.runtime.test
        def it_has_zone(sut, zone_id):
            return assert_output_equals(sut.cname_record.zone_id, zone_id)

        @pulumi.runtime.test
        def it_points_to_load_balancer(sut, load_balancer_dns_name):
            return assert_output_equals(sut.cname_record.content, load_balancer_dns_name)

    def describe_cert():
        @pulumi.runtime.test
        def it_has_cert(sut):
            assert sut.cert

        @pulumi.runtime.test
        def it_has_fqdn(sut, app_name, environment):
            return assert_output_equals(sut.cert.domain_name, f"{environment}-{app_name}.strongmind.com")

        @pulumi.runtime.test
        def it_validates_with_dns(sut):
            return assert_output_equals(sut.cert.validation_method, "DNS")

        @pulumi.runtime.test
        def it_adds_validation_record(sut):
            assert sut.cert_validation_record

        @pulumi.runtime.test
        def it_adds_validation_record_with_name(sut, resource_record_name):
            return assert_output_equals(sut.cert_validation_record.name, resource_record_name)

        @pulumi.runtime.test
        def it_adds_validation_record_with_type(sut, resource_record_type):
            return assert_output_equals(sut.cert_validation_record.type, resource_record_type)

        @pulumi.runtime.test
        def it_adds_validation_record_with_zone_id(sut, zone_id):
            return assert_output_equals(sut.cert_validation_record.zone_id, zone_id)

        @pulumi.runtime.test
        def it_adds_validation_record_with_value(sut, resource_record_value):
            return assert_output_equals(sut.cert_validation_record.content, resource_record_value)

        @pulumi.runtime.test
        def it_adds_validation_record_with_ttl(sut):
            return assert_output_equals(sut.cert_validation_record.ttl, 1)

        @pulumi.runtime.test
        def it_adds_validation_cert(sut):
            assert sut.cert_validation_cert

        @pulumi.runtime.test
        def it_adds_validation_cert_with_cert_arn(sut):
            return assert_outputs_equal(sut.cert_validation_cert.certificate_arn, sut.cert.arn)

        @pulumi.runtime.test
        def it_adds_validation_cert_with_fqdns(sut):
            return assert_outputs_equal(sut.cert_validation_cert.validation_record_fqdns,
                                        [sut.cert_validation_record.hostname])

        def describe_with_a_custom_namespace():
            @pytest.fixture
            def namespace(faker):
                return faker.word()

            @pytest.fixture
            def component_kwargs(component_kwargs, namespace):
                component_kwargs["namespace"] = namespace
                return component_kwargs

            @pulumi.runtime.test
            def it_has_a_custom_namespace(sut, namespace):
                return assert_outputs_equal(sut.namespace, namespace)

            @pulumi.runtime.test
            def it_has_fqdn(sut, namespace):
                return assert_output_equals(sut.cert.domain_name, f"{namespace}.strongmind.com")

    def describe_with_existing_cluster():
        @pytest.fixture
        def existing_cluster_arn(faker):
            return faker.word()

        @pytest.fixture
        def sut(component_kwargs, existing_cluster_arn):
            component_kwargs["need_load_balancer"] = False
            component_kwargs["ecs_cluster_arn"] = existing_cluster_arn
            import strongmind_deployment.container
            return strongmind_deployment.container.ContainerComponent("container",
                                                                      **component_kwargs)

        @pulumi.runtime.test
        def it_uses_existing_cluster(sut, existing_cluster_arn):
            return assert_output_equals(sut.fargate_service.cluster, existing_cluster_arn)

    def describe_logs():
        @pulumi.runtime.test
        def it_creates_a_log_group(sut, stack, app_name):
            return assert_output_equals(sut.logs.name, f"/aws/ecs/{app_name}-{stack}")

        @pulumi.runtime.test
        def it_sets_retention(sut):
            return assert_output_equals(sut.logs.retention_in_days, 14)

        @pulumi.runtime.test
        def it_has_no_filters(sut):
            return sut.log_metric_filters == []

        def describe_with_job_filters():
            @pytest.fixture
            def waiting_workers_pattern():
                return "[LETTER, DATE, LEVEL, SEP, N, I, HAVE, WAITING_JOBS, JOBS, FOR, WAITING_WORKERS, " \
                       "WAITING=waiting, WORKERS=workers]"

            @pytest.fixture
            def waiting_jobs_pattern():
                return "[LETTER, DATE, LEVEL, SEP, N, I, HAVE, WAITING_JOBS, JOBS, FOR, WAITING_WORKERS, " \
                       "WAITING=waiting, WORKERS=workers]"

            @pytest.fixture
            def waiting_workers_metric_value():
                return "$WAITING_WORKERS"

            @pytest.fixture
            def waiting_jobs_metric_value():
                return "$WAITING_JOBS"

            @pytest.fixture
            def log_metric_filters(waiting_workers_pattern, waiting_jobs_pattern,
                                   waiting_workers_metric_value, waiting_jobs_metric_value):
                return [
                    {
                        "pattern": waiting_workers_pattern,
                        "metric_transformation": {
                            "name": "waiting_workers",
                            "namespace": "Jobs",
                            "value": waiting_workers_metric_value,
                        }
                    },
                    {
                        "pattern": waiting_jobs_pattern,
                        "metric_transformation": {
                            "name": "waiting_jobs",
                            "namespace": "Jobs",
                            "value": waiting_jobs_metric_value,
                        }
                    }
                ]

            @pytest.fixture
            def component_kwargs(component_kwargs, log_metric_filters):
                component_kwargs["log_metric_filters"] = log_metric_filters
                return component_kwargs

            @pulumi.runtime.test
            def it_creates_metric_filters(sut):
                assert sut.log_metric_filters

            @pulumi.runtime.test
            def it_sets_the_workers_pattern(sut, waiting_workers_pattern):
                return assert_output_equals(sut.log_metric_filters[0].pattern, waiting_workers_pattern)

            @pulumi.runtime.test
            def it_sets_the_workers_metric_name(sut):
                return assert_output_equals(sut.log_metric_filters[0].metric_transformation.name,
                                            sut.namespace + "-waiting_workers")

            @pulumi.runtime.test
            def it_sets_the_workers_values(sut, waiting_workers_metric_value):
                return assert_output_equals(sut.log_metric_filters[0].metric_transformation.value,
                                            waiting_workers_metric_value)

            @pulumi.runtime.test
            def it_sets_the_workers_namespace(sut):
                return assert_output_equals(sut.log_metric_filters[0].metric_transformation.namespace,
                                            "Jobs")

            @pulumi.runtime.test
            def it_sets_the_jobs_pattern(sut, waiting_jobs_pattern):
                return assert_output_equals(sut.log_metric_filters[1].pattern, waiting_jobs_pattern)

            @pulumi.runtime.test
            def it_sets_the_jobs_metric_name(sut):
                return assert_output_equals(sut.log_metric_filters[1].metric_transformation.name,
                                            sut.namespace + "-waiting_jobs")

            @pulumi.runtime.test
            def it_sets_the_jobs_values(sut, waiting_jobs_metric_value):
                return assert_output_equals(sut.log_metric_filters[1].metric_transformation.value,
                                            waiting_jobs_metric_value)

            @pulumi.runtime.test
            def it_sets_the_jobs_namespace(sut):
                return assert_output_equals(sut.log_metric_filters[1].metric_transformation.namespace,
                                            "Jobs")

    def describe_healthy_host_metric_alarm():
        @pulumi.runtime.test
        def it_exits(sut):
            assert hasattr(sut, 'healthy_host_metric_alarm')
            assert sut.healthy_host_metric_alarm is not None

        @pulumi.runtime.test
        def it_is_named_healthy_host_metric_alarm(sut, app_name, stack):
            return assert_output_equals(sut.healthy_host_metric_alarm.name, f"{app_name}-{stack}-healthy-host-metric-alarm")

        @pulumi.runtime.test
        def it_triggers_when_less_than_threshold(sut):
            return assert_output_equals(sut.healthy_host_metric_alarm.comparison_operator, "LessThanThreshold")

        @pulumi.runtime.test
        def it_evaluates_for_one_period(sut):
            return assert_output_equals(sut.healthy_host_metric_alarm.evaluation_periods, 1)

        @pulumi.runtime.test
        def it_triggers_based_on_mathematical_expression(sut):
            return assert_output_equals(sut.healthy_host_metric_alarm.metric_queries[0].expression, "SUM(METRICS())")

        @pulumi.runtime.test
        def it_checks_the_unit_as_a_count(sut):
            return assert_output_equals(sut.healthy_host_metric_alarm.metric_queries[1].metric.stat, "Maximum")

        @pulumi.runtime.test
        def it_belongs_to_the_ECS_namespace(sut):
            return assert_output_equals(sut.healthy_host_metric_alarm.metric_queries[1].metric.namespace,
                                        "AWS/ApplicationELB")

        @pulumi.runtime.test
        def it_runs_every_minute(sut):
            return assert_output_equals(sut.healthy_host_metric_alarm.metric_queries[1].metric.period, 60)

        @pulumi.runtime.test
        def it_triggers_when_the_threshold_is_less_than_the_desired_count(sut):
            expected_threshold = sut.desired_count
            actual_threshold = sut.healthy_host_metric_alarm.threshold
            assert_output_equals(actual_threshold, expected_threshold)

        @pulumi.runtime.test
        def it_has_tags(sut):
            assert sut.healthy_host_metric_alarm.tags

    def describe_unhealthy_host_metric_alarm():
        @pulumi.runtime.test
        def it_exits(sut):
            assert hasattr(sut, 'unhealthy_host_metric_alarm')
            assert sut.unhealthy_host_metric_alarm is not None

        @pulumi.runtime.test
        def it_is_named_unhealthy_host_metric_alarm(sut, app_name, stack):
            return assert_output_equals(sut.unhealthy_host_metric_alarm.name, f"{app_name}-{stack}-unhealthy-host-metric-alarm")

        @pulumi.runtime.test
        def it_triggers_when_greater_than_threshold(sut):
            return assert_output_equals(sut.unhealthy_host_metric_alarm.comparison_operator, "GreaterThanThreshold")

        @pulumi.runtime.test
        def it_evaluates_for_one_period(sut):
            return assert_output_equals(sut.unhealthy_host_metric_alarm.evaluation_periods, 1)

        @pulumi.runtime.test
        def it_triggers_based_on_mathematical_expression(sut):
            return assert_output_equals(sut.unhealthy_host_metric_alarm.metric_queries[0].expression, "SUM(METRICS())")

        @pulumi.runtime.test
        def it_checks_the_unit_as_a_count(sut):
            return assert_output_equals(sut.unhealthy_host_metric_alarm.metric_queries[1].metric.stat, "Maximum")

        @pulumi.runtime.test
        def it_belongs_to_the_ECS_namespace(sut):
            return assert_output_equals(sut.unhealthy_host_metric_alarm.metric_queries[1].metric.namespace,
                                        "AWS/ApplicationELB")

        @pulumi.runtime.test
        def it_runs_every_minute(sut):
            return assert_output_equals(sut.unhealthy_host_metric_alarm.metric_queries[1].metric.period, 60)

        @pulumi.runtime.test
        def it_triggers_when_the_threshold_is_more_than_25percent_of_desired_count(sut):
            desired_count = sut.desired_count
            expected_threshold = desired_count * 0.25
            actual_threshold = sut.unhealthy_host_metric_alarm.threshold
            assert_output_equals(actual_threshold, expected_threshold)

        @pulumi.runtime.test
        def it_has_tags(sut):
            assert sut.unhealthy_host_metric_alarm.tags

    def it_sets_the_namespace_to_the_project_and_stack(sut, app_name, stack):
        assert sut.namespace == f"{app_name}-{stack}"

    def describe_with_a_non_container_default_name():
        @pytest.fixture
        def component_name(faker):
            return faker.word()

        @pytest.fixture
        def sut(component_kwargs, component_name):
            import strongmind_deployment.container
            return strongmind_deployment.container.ContainerComponent(component_name,
                                                                      **component_kwargs
                                                                      )

        def it_adds_the_component_name_to_the_namespace(sut, app_name, stack, component_name):
            assert sut.namespace == f"{app_name}-{stack}-{component_name}"

    def describe_with_a_custom_namespace():
        @pytest.fixture
        def namespace(faker):
            return f"{faker.word()}-{faker.word()}-namespace"

        @pytest.fixture
        def component_kwargs(component_kwargs, namespace):
            component_kwargs["namespace"] = namespace
            return component_kwargs

        @pulumi.runtime.test
        def it_has_a_namespace(sut, namespace):
            assert sut.namespace == namespace

        @pulumi.runtime.test
        def it_sets_the_alb_namespace(sut, namespace):
            assert sut.alb.namespace == namespace

        def describe_with_a_non_container_default_name():
            @pytest.fixture
            def component_name(faker):
                return faker.word()

            @pytest.fixture
            def sut(component_kwargs, component_name):
                import strongmind_deployment.container
                return strongmind_deployment.container.ContainerComponent(component_name,
                                                                          **component_kwargs
                                                                          )

            @pulumi.runtime.test
            def it_adds_the_component_name_to_the_namespace(sut, namespace, component_name):
                assert sut.namespace == f"{namespace}-{component_name}"
