import pulumi_aws as aws
import pulumi_awsx as awsx

OTLP_HTTP_PORT = 4318
AGENT_CONTAINER_NAME = "datadog-agent"
AGENT_IMAGE = "gcr.io/datadoghq/agent:7.84.5"
DD_API_KEY_SECRET_NAME = "datadog/ecs-agent-api-key"


def otel_env_vars(service_name, env_name, container_image, health_check_path):
    """OpenTelemetry settings that point the app container at the agent sidecar.

    Values assume the Ruby SDK, which reads OTEL_EXPORTER_OTLP_TIMEOUT in seconds; non-Ruby apps
    should set their own OTEL_EXPORTER_OTLP_TIMEOUT in env_vars (spec unit is milliseconds).
    """
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
