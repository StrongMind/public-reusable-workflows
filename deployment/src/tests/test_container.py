import json
import os

import boto3
import pulumi.runtime
import pytest
from moto import mock_aws
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
                                "bedrock:ListInferenceProfiles",
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
                                "s3:ListBucket",
                                "ses:SendEmail",
                                "ses:SendRawEmail"
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

            def describe_desired_count():
                @pytest.fixture
                def desired_count():
                    import random
                    return random.randint(10, 100)

                @pytest.fixture
                def component_kwargs(component_kwargs, desired_count):
                    component_kwargs["desired_count"] = desired_count
                    return component_kwargs

                @pulumi.runtime.test
                def it_sets_the_desired_count(sut, desired_count):
                    return assert_output_equals(sut.fargate_service.desired_count, desired_count)

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
            
    def describe_with_cloudfront():
        @pulumi.runtime.test
        def it_creates_a_cloudfront_distribution(sut):
            assert sut.cloudfront_distribution

        @pulumi.runtime.test
        def it_has_a_cloudfront_certificate(sut):
            assert sut.cloudfront_cert

        @pulumi.runtime.test
        def it_creates_cloudfront_certificate_in_us_east_1(sut):
            def check_region(args):
                arn = args[0]
                # ARN format: arn:aws:acm:REGION:ACCOUNT:certificate/UUID
                assert ":us-east-1:" in arn, "Certificate must be created in us-east-1 for CloudFront"

            return pulumi.Output.all(sut.cloudfront_cert.arn).apply(check_region)

        @pulumi.runtime.test
        def it_has_a_certificate_validation_record(sut):
            assert sut.cloudfront_cert_validation_record

        @pulumi.runtime.test
        def it_sets_certificate_validation_record_name_from_options(sut):
            def check_name(args):
                record_name, validation_options = args
                expected_name = validation_options[0]['resource_record_name']
                assert record_name == expected_name

            return pulumi.Output.all(
                sut.cloudfront_cert_validation_record.name,
                sut.cloudfront_cert.domain_validation_options
            ).apply(check_name)

        @pulumi.runtime.test
        def it_sets_certificate_validation_record_type_from_options(sut):
            def check_type(args):
                record_type, validation_options = args
                expected_type = validation_options[0]['resource_record_type']
                assert record_type == expected_type

            return pulumi.Output.all(
                sut.cloudfront_cert_validation_record.type,
                sut.cloudfront_cert.domain_validation_options
            ).apply(check_type)

        @pulumi.runtime.test
        def it_sets_certificate_validation_record_content_from_options(sut):
            def check_content(args):
                record_content, validation_options = args
                validation_value = validation_options[0]['resource_record_value']
                # Remove trailing period if present
                expected_content = validation_value[:-1] if validation_value.endswith('.') else validation_value
                assert record_content == expected_content

            return pulumi.Output.all(
                sut.cloudfront_cert_validation_record.content,
                sut.cloudfront_cert.domain_validation_options
            ).apply(check_content)

        @pulumi.runtime.test
        def it_sets_certificate_validation_record_ttl(sut):
            return assert_output_equals(sut.cloudfront_cert_validation_record.ttl, 1)

        @pulumi.runtime.test
        def it_sets_certificate_validation_record_zone_id(sut):
            return assert_output_equals(sut.cloudfront_cert_validation_record.zone_id, "b4b7fec0d0aacbd55c5a259d1e64fff5")

        @pulumi.runtime.test
        def it_has_certificate_validation(sut):
            assert sut.cloudfront_cert_validation

        @pulumi.runtime.test
        def it_sets_certificate_validation_certificate_arn(sut):
            return assert_outputs_equal(sut.cloudfront_cert_validation.certificate_arn, sut.cloudfront_cert.arn)

        @pulumi.runtime.test
        def it_sets_certificate_validation_record_fqdns(sut):
            def check_fqdns(args):
                validation_fqdns, record_hostname = args
                assert validation_fqdns == [record_hostname]

            return pulumi.Output.all(
                sut.cloudfront_cert_validation.validation_record_fqdns,
                sut.cloudfront_cert_validation_record.hostname
            ).apply(check_fqdns)

        @pulumi.runtime.test
        def it_configures_cloudfront_with_correct_aliases(sut, stack, app_name):
            def check_aliases(args):
                aliases = args[0]
                expected_alias = f"{stack}-{app_name}.strongmind.com" if stack != "prod" else f"{app_name}.strongmind.com"
                assert aliases == [expected_alias]

            return pulumi.Output.all(sut.cloudfront_distribution.aliases).apply(check_aliases)

        @pulumi.runtime.test
        def it_configures_cloudfront_with_correct_origins(sut, stack):
            def check_origins(args):
                alb_origin, s3_origin, alb_dns_name = args
                # Check ALB origin
                assert alb_origin["domain_name"] == alb_dns_name
                assert alb_origin["origin_id"] == alb_dns_name
                assert alb_origin["custom_origin_config"]["origin_protocol_policy"] == "https-only"
                assert alb_origin["custom_origin_config"]["origin_ssl_protocols"] == ["TLSv1.2"]
                
                # Check S3 origin
                cdn_bucket = "strongmind-cdn-stage" if stack != "prod" else "strongmind-cdn-prod"
                expected_s3_domain = f"{cdn_bucket}.s3.us-west-2.amazonaws.com"
                assert s3_origin["domain_name"] == expected_s3_domain
                assert s3_origin["origin_id"] == expected_s3_domain

            return pulumi.Output.all(
                sut.cloudfront_distribution.origins[0],
                sut.cloudfront_distribution.origins[1],
                sut.load_balancer.dns_name
            ).apply(check_origins)
        
        @pulumi.runtime.test
        def it_configures_cloudfront_with_correct_cache_behavior(sut):
            assert sut.cloudfront_distribution.default_cache_behavior
            
        @pulumi.runtime.test
        def it_has_a_viewer_certificate(sut):
            assert sut.cloudfront_distribution.viewer_certificate

        @pulumi.runtime.test
        def it_uses_the_sni_only_method_for_the_viewer_certificate(sut):
            def check_ssl_method(args):
                viewer_cert = args[0]
                assert viewer_cert.get("ssl_support_method") == "sni-only"

            return pulumi.Output.all(sut.cloudfront_distribution.viewer_certificate).apply(check_ssl_method)

        @pulumi.runtime.test
        def it_uses_the_tls_v1_2_protocol_for_the_viewer_certificate(sut):
            def check_protocol_version(args):
                viewer_cert = args[0]
                assert viewer_cert.get("minimum_protocol_version") == "TLSv1.2_2021"

            return pulumi.Output.all(sut.cloudfront_distribution.viewer_certificate).apply(check_protocol_version)

        @pulumi.runtime.test
        def it_has_a_default_root_object(sut):
            def check_root_object(args):
                root_object = args[0]
                if isinstance(root_object, list):
                    assert root_object[0] == ""
                else:
                    assert root_object == ""

            return pulumi.Output.all(sut.cloudfront_distribution.default_root_object).apply(check_root_object)
            
        @pulumi.runtime.test
        def it_has_an_ordered_cache_behavior_for_error_pages(sut):
            assert sut.cloudfront_distribution.ordered_cache_behaviors

        @pulumi.runtime.test
        def it_configures_ordered_cache_behavior_correctly(sut, stack):
            def check_cache_behavior(args):
                behaviors = args[0]
                behavior = behaviors[0]  # We only have one ordered cache behavior
                
                # Check path pattern
                assert behavior["path_pattern"] == "/504.html"
                
                # Check origin
                cdn_bucket = "strongmind-cdn-stage" if stack != "prod" else "strongmind-cdn-prod"
                expected_origin = f"{cdn_bucket}.s3.us-west-2.amazonaws.com"
                assert behavior["target_origin_id"] == expected_origin
                
                # Check methods
                assert behavior["allowed_methods"] == ["GET", "HEAD"]
                assert behavior["cached_methods"] == ["GET", "HEAD"]
                
                # Check protocol and compression
                assert behavior["viewer_protocol_policy"] == "allow-all"
                assert behavior["compress"] is True
                
                # Check policy IDs are set (we can't check exact values as they're looked up)
                assert behavior["cache_policy_id"] is not None
                assert behavior["response_headers_policy_id"] is not None

            return pulumi.Output.all(sut.cloudfront_distribution.ordered_cache_behaviors).apply(check_cache_behavior)
        
        @pulumi.runtime.test
        def it_has_a_default_cache_behavior(sut):
            assert sut.cloudfront_distribution.default_cache_behavior

        @pulumi.runtime.test
        def it_configures_default_cache_behavior_correctly(sut):
            def check_default_cache_behavior(args):
                behavior, alb_dns_name = args
                
                # Check target origin
                assert behavior["target_origin_id"] == alb_dns_name
                
                # Check protocol policy
                assert behavior["viewer_protocol_policy"] == "redirect-to-https"
                
                # Check methods
                assert set(behavior["allowed_methods"]) == {"GET", "HEAD", "OPTIONS", "PUT", "PATCH", "POST", "DELETE"}
                assert set(behavior["cached_methods"]) == {"GET", "HEAD"}
                
                # Check compression
                assert behavior["compress"] is True
                
                # Check policy IDs are set
                assert behavior["cache_policy_id"] is not None
                assert behavior["origin_request_policy_id"] is not None

            return pulumi.Output.all(
                sut.cloudfront_distribution.default_cache_behavior,
                sut.load_balancer.dns_name
            ).apply(check_default_cache_behavior)
        
        @pulumi.runtime.test
        def it_has_custom_error_responses(sut):
            assert sut.cloudfront_distribution.custom_error_responses

        @pulumi.runtime.test
        def it_configures_custom_error_responses_correctly(sut):
            def check_error_responses(args):
                error_responses = args[0]
                error_response = error_responses[0]  # We only have one error response
                
                # Check error and response codes
                assert error_response["error_code"] == 504
                assert error_response["response_code"] == 504
                
                # Check response page path
                assert error_response["response_page_path"] == "/504.html"
                
                # Check caching TTL
                assert error_response["error_caching_min_ttl"] == 10

            return pulumi.Output.all(sut.cloudfront_distribution.custom_error_responses).apply(check_error_responses)
        
        @pulumi.runtime.test
        def it_has_restrictions(sut):
            assert sut.cloudfront_distribution.restrictions

        @pulumi.runtime.test
        def it_configures_restrictions_correctly(sut):
            def check_restrictions(args):
                restrictions = args[0]
                assert restrictions["geo_restriction"]["restriction_type"] == "none"

            return pulumi.Output.all(sut.cloudfront_distribution.restrictions).apply(check_restrictions)

        @pulumi.runtime.test
        def it_has_tags(sut):
            assert sut.cloudfront_distribution.tags

        @pulumi.runtime.test
        def it_has_a_cname_record(sut):
            assert sut.cname_record

        @pulumi.runtime.test
        def it_sets_cname_record_type(sut):
            return assert_output_equals(sut.cname_record.type, "CNAME")

        @pulumi.runtime.test
        def it_sets_cname_record_content(sut):
            return assert_outputs_equal(sut.cname_record.content, sut.cloudfront_distribution.domain_name)

        @pulumi.runtime.test
        def it_sets_cname_record_name(sut, stack, app_name):
            expected_name = f"{stack}-{app_name}" if stack != "prod" else app_name
            return assert_output_equals(sut.cname_record.name, expected_name)

        @pulumi.runtime.test
        def it_sets_cname_record_zone_id(sut):
            return assert_output_equals(sut.cname_record.zone_id, "b4b7fec0d0aacbd55c5a259d1e64fff5")
        
    def describe_with_repository_domain_name_certificate():
        @pulumi.runtime.test
        def it_sets_certificate_domain_name_correctly(sut, stack, app_name):
            def check_domain_name(args):
                domain_name = args[0]
                expected_domain = f"{stack}-{app_name}.strongmind.com" if stack != "prod" else f"{app_name}.strongmind.com"
                assert domain_name == expected_domain

            return pulumi.Output.all(sut.cloudfront_cert.domain_name).apply(check_domain_name)

        @pulumi.runtime.test
        def it_uses_dns_validation_method(sut):
            return assert_output_equals(sut.cloudfront_cert.validation_method, "DNS")

        def describe_with_custom_namespace():
            @pytest.fixture
            def namespace(faker):
                return faker.word()

            @pytest.fixture
            def component_kwargs(component_kwargs, namespace):
                component_kwargs["namespace"] = namespace
                return component_kwargs

            @pulumi.runtime.test
            def it_uses_namespace_for_certificate_domain(sut, namespace):
                def check_domain_name(args):
                    domain_name = args[0]
                    expected_domain = f"{namespace}.strongmind.com"
                    assert domain_name == expected_domain

                return pulumi.Output.all(sut.cloudfront_cert.domain_name).apply(check_domain_name)

        @pulumi.runtime.test
        def it_has_tags(sut):
            assert sut.cloudfront_cert.tags

    def describe_with_existing_cluster():
        @pytest.fixture
        def existing_cluster():
            import pulumi_aws as aws
            return aws.ecs.Cluster("existing-cluster")

        @pytest.fixture
        def sut(component_kwargs, existing_cluster):
            component_kwargs["need_load_balancer"] = False
            component_kwargs["ecs_cluster"] = existing_cluster
            import strongmind_deployment.container
            return strongmind_deployment.container.ContainerComponent("container",
                                                                      **component_kwargs)

        @pulumi.runtime.test
        def it_uses_existing_cluster(sut, existing_cluster):
            assert sut.ecs_cluster == existing_cluster

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

    def describe_unhealthy_host_metric_alarm():
        @pulumi.runtime.test
        def it_exits(sut):
            assert sut.unhealthy_host_metric_alarm

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
            return assert_output_equals(sut.unhealthy_host_metric_alarm.metric_queries[0].expression, "IF(desired_tasks > 0, unhealthy_hosts / desired_tasks, 0)")

        @pulumi.runtime.test
        def it_checks_the_unit_as_a_count(sut):
            return assert_output_equals(sut.unhealthy_host_metric_alarm.metric_queries[1].metric.stat, "Maximum")

        @pulumi.runtime.test
        def it_belongs_to_the_ECS_namespace(sut):
            return assert_output_equals(sut.unhealthy_host_metric_alarm.metric_queries[2].metric.namespace, "ECS/ContainerInsights")

        @pulumi.runtime.test
        def it_runs_every_minute(sut):
            return assert_output_equals(sut.unhealthy_host_metric_alarm.metric_queries[2].metric.period, 60)

        @pulumi.runtime.test
        def it_triggers_when_the_threshold_is_more_than_25percent_of_desired_count(sut):
            return assert_output_equals(sut.unhealthy_host_metric_alarm.threshold, 0.25)

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
