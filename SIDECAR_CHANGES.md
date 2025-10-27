# Sidecar Container Support - Changes Summary

## Overview

Added support for sidecar containers in ECS Fargate deployments. This allows running additional containers (like Datadog agent, log shippers, service mesh proxies) alongside application containers.

## Files Modified

### 1. `deployment/src/strongmind_deployment/container.py`

**Changes:**
- **Line 56-57**: Added `sidecar_containers` parameter to docstring
- **Line 85**: Added `self.sidecar_containers = kwargs.get('sidecar_containers', [])`
- **Lines 278-316**: Refactored task definition creation to support multiple containers

**What it does:**
- Accepts a list of additional container definitions
- Creates task definitions with multiple containers when sidecars are provided
- Maintains backward compatibility (single container when no sidecars)

**Example Usage:**
```python
from strongmind_deployment.container import ContainerComponent
import pulumi_awsx as awsx

sidecar = awsx.ecs.TaskDefinitionContainerDefinitionArgs(
    name="datadog-agent",
    image="gcr.io/datadoghq/agent:7",
    cpu=100,
    memory=256,
    # ... other config
)

container = ContainerComponent(
    "my-container",
    container_image="my-app:latest",
    sidecar_containers=[sidecar],
    # ... other kwargs
)
```

### 2. `deployment/src/strongmind_deployment/rails.py`

**Changes:**
- **Lines 79-80**: Added `sidecar_containers` parameter to docstring

**What it does:**
- Documents the parameter for RailsComponent
- No code changes needed (automatically passes through via `**kwargs`)
- Sidecars are applied to both web and worker containers

**Example Usage:**
```python
from strongmind_deployment.rails import RailsComponent

rails = RailsComponent(
    "my-rails-app",
    sidecar_containers=[datadog_agent_container],
    # ... other kwargs
)
```

## Backward Compatibility

✅ **Fully backward compatible**
- Existing code without `sidecar_containers` works unchanged
- Defaults to empty list if not provided
- Uses singular `container` parameter when no sidecars
- Uses plural `containers` parameter when sidecars exist

## Use Cases

### 1. Application Performance Monitoring (Datadog)
```python
datadog_agent = awsx.ecs.TaskDefinitionContainerDefinitionArgs(
    name="datadog-agent",
    image="gcr.io/datadoghq/agent:7",
    cpu=100,
    memory=256,
    essential=False,
    environment=[
        {"name": "DD_SITE", "value": "datadoghq.com"},
        {"name": "DD_APM_ENABLED", "value": "true"},
        {"name": "ECS_FARGATE", "value": "true"},
    ],
    secrets=[{"name": "DD_API_KEY", "valueFrom": "arn:aws:..."}]
)
```

### 2. Log Shipping (Fluentd)
```python
fluentd = awsx.ecs.TaskDefinitionContainerDefinitionArgs(
    name="fluentd",
    image="fluent/fluentd:latest",
    cpu=50,
    memory=128,
    essential=False,
)
```

### 3. Service Mesh (Envoy)
```python
envoy = awsx.ecs.TaskDefinitionContainerDefinitionArgs(
    name="envoy",
    image="envoyproxy/envoy:latest",
    cpu=100,
    memory=256,
    essential=False,
)
```

## Testing

### Unit Tests (if applicable)
```python
def test_sidecar_containers():
    # Test that sidecars are properly added to task definition
    pass
```

### Integration Test
1. Deploy a container with sidecars
2. Verify task definition has multiple containers
3. Verify both containers start and run

## Migration Guide

### Before (No Sidecars)
```python
component = RailsComponent(
    "rails",
    cpu=2048,
    memory=4096,
    env_vars={'MY_VAR': 'value'}
)
```

### After (With Sidecars)
```python
datadog_sidecar = awsx.ecs.TaskDefinitionContainerDefinitionArgs(
    name="datadog-agent",
    image="gcr.io/datadoghq/agent:7",
    cpu=100,
    memory=256,
    essential=False,
)

component = RailsComponent(
    "rails",
    cpu=2048,
    memory=4096,
    env_vars={
        'MY_VAR': 'value',
        'DD_AGENT_HOST': 'localhost',  # Can talk to sidecar via localhost
    },
    sidecar_containers=[datadog_sidecar]  # Add this line
)
```

## Benefits

1. **Resource Isolation**: Sidecars have independent CPU/memory limits
2. **Independent Updates**: Update monitoring without rebuilding app
3. **Failure Isolation**: Sidecar failure doesn't kill main container (if `essential=False`)
4. **Reusability**: Same sidecar image across all services
5. **Best Practice**: Industry-standard pattern for Kubernetes, ECS, etc.

## Notes

- Sidecars share the same network namespace (can communicate via `localhost`)
- Sidecars share the same task lifecycle (start/stop together)
- Set `essential=False` on sidecars to prevent them from killing the task if they fail
- Total task CPU/memory = sum of all containers

## Deployment

1. Create PR with these changes
2. Get code review
3. Merge to main
4. Package is automatically available for all projects
5. Projects can now use `sidecar_containers` parameter

## Questions?

Contact the platform team or see:
- [ECS Task Definition Docs](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definitions.html)
- [Fargate Sidecar Pattern](https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/fargate-sidecar.html)

