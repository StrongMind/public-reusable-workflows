import pulumi
import pulumi_aws as aws
import pulumi_awsx as awsx
import pulumi_datadog

OTLP_HTTP_PORT = 4318
AGENT_CONTAINER_NAME = "datadog-agent"
AGENT_IMAGE = "gcr.io/datadoghq/agent:7.84.5"
DD_API_KEY_SECRET_NAME = "datadog/ecs-agent-api-key"
MONITORS_API_KEY_SECRET_NAME = "datadog/pulumi-monitors-api-key"
MONITORS_APP_KEY_SECRET_NAME = "datadog/pulumi-monitors-app-key"


def otel_env_vars(service_name, env_name, container_image, health_check_path):
    """OpenTelemetry settings that point the app container at the agent sidecar.

    Values assume the Ruby SDK, which reads OTEL_EXPORTER_OTLP_TIMEOUT in seconds; non-Ruby apps
    should set their own OTEL_EXPORTER_OTLP_TIMEOUT in env_vars (spec unit is milliseconds).
    """
    if not isinstance(container_image, str):
        raise ValueError("datadog=True needs container_image as a 'repo:tag' string; the tag becomes service.version")
    git_sha = container_image.split(':')[-1]
    return {
        "OTEL_SERVICE_NAME": service_name,
        "OTEL_EXPORTER_OTLP_ENDPOINT": f"http://localhost:{OTLP_HTTP_PORT}",
        "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
        "OTEL_EXPORTER_OTLP_TIMEOUT": "2",
        "OTEL_BSP_EXPORT_TIMEOUT": "2000",
        "OTEL_RUBY_INSTRUMENTATION_RACK_CONFIG_OPTS": f"untraced_endpoints={health_check_path}",
        "OTEL_RESOURCE_ATTRIBUTES": (
            f"deployment.environment.name={env_name},"
            f"service.version={git_sha}"
        ),
    }


def agent_sidecar(env_name):
    """Datadog agent that receives OTLP from the app container; cpu 0 keeps the task at the app's size."""
    api_key_secret_arn = aws.secretsmanager.get_secret_output(name=DD_API_KEY_SECRET_NAME).arn
    return awsx.ecs.TaskDefinitionContainerDefinitionArgs(
        name=AGENT_CONTAINER_NAME,
        image=AGENT_IMAGE,
        cpu=0,
        memory=256,
        essential=False,
        environment=[
            {"name": "DD_SITE", "value": "datadoghq.com"},
            {"name": "ECS_FARGATE", "value": "true"},
            {"name": "DD_ENV", "value": env_name},
            {"name": "DD_APM_ENABLED", "value": "true"},
            {"name": "DD_OTLP_CONFIG_RECEIVER_PROTOCOLS_HTTP_ENDPOINT", "value": f"localhost:{OTLP_HTTP_PORT}"},
            {"name": "DD_LOGS_ENABLED", "value": "false"},
            {"name": "DD_CONTAINER_EXCLUDE", "value": "name:.*"},
            {"name": "DD_PROCESS_AGENT_ENABLED", "value": "false"},
            {"name": "DD_SYSTEM_PROBE_ENABLED", "value": "false"},
        ],
        secrets=[{"name": "DD_API_KEY", "valueFrom": api_key_secret_arn}],
        log_configuration=awsx.ecs.TaskDefinitionLogConfigurationArgs(
            log_driver="awslogs",
            options={"awslogs-region": "us-west-2", "awslogs-stream-prefix": AGENT_CONTAINER_NAME},
        ),
    )


def error_monitor(name, service_name, env_name, notify, owner, parent):
    """Alerts `notify` on each new Datadog Error Tracking issue for the service in this environment."""
    provider = pulumi_datadog.Provider(
        f"{name}-datadog",
        api_key=_secret_string(MONITORS_API_KEY_SECRET_NAME),
        app_key=_secret_string(MONITORS_APP_KEY_SECRET_NAME),
        opts=pulumi.ResourceOptions(parent=parent),
    )
    return pulumi_datadog.Monitor(
        f"{name}-new-error",
        name=f"{service_name}: [{{{{ issue.alert_reason }}}}] New issue to review",
        type="error-tracking alert",
        query=(
            f'error-tracking("service:{service_name} env:{env_name}").source("all")'
            '.new().rollup("count").by("issue.id").last("1d") > 0'
        ),
        message=(
            f"A new [issue]({{{{ issue.link }}}}) was detected in {service_name} {env_name}.\n\n"
            "{{#is_alert}}\n"
            "```\n"
            "{{issue.attributes.error.type}}: {{issue.attributes.error.message}}\n"
            "```\n\n"
            f"{notify}\n"
            "{{/is_alert}}\n\n"
            "Mark the issue as Reviewed to stop receiving this alert."
        ),
        tags=[f"service:{service_name}", f"env:{env_name}", f"owner:{owner}"],
        priority="3",
        include_tags=False,
        notify_audit=False,
        monitor_thresholds=pulumi_datadog.MonitorMonitorThresholdsArgs(critical="0"),
        opts=pulumi.ResourceOptions(parent=parent, provider=provider),
    )


def _secret_string(secret_name):
    return pulumi.Output.secret(aws.secretsmanager.get_secret_version_output(secret_id=secret_name).secret_string)
