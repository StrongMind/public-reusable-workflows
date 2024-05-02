import pulumi
import pulumi_aws as aws

def create_compute_environment(
    name,
    max_vcpus,
    security_group_ids,
    subnets,
    image_id,
    tags,
    service_role
    ):

    create_env = aws.batch.ComputeEnvironment(f"{name}-batch",
        compute_environment_name=f"{name}-batch",
        compute_resources=aws.batch.ComputeEnvironmentComputeResourcesArgs(
            max_vcpus=max_vcpus,
            security_group_ids=security_group_ids,
            subnets=subnets,
            type="FARGATE",
            ),
        type="MANAGED",
        tags=tags,
        service_role=service_role
        )
    return create_env

def scheduling_policy(name,tags
    ):
    sch_policy = aws.batch.SchedulingPolicy(f"{name}-sch_policy",
         fair_share_policy=aws.batch.SchedulingPolicyFairSharePolicyArgs(
             share_distributions=[
                 aws.batch.SchedulingPolicyFairSharePolicyShareDistributionArgs(
                     share_identifier="*",
                     weight_factor=1
                 )
            ]
         ),
         tags=tags
    )
    return sch_policy


def job_queue(name,
    create_env,
    priority,
    tags
):
    queue = aws.batch.JobQueue(f"{name}-queue",
        compute_environments=[create_env],
        priority=priority,
        state="ENABLED",
        tags=tags
        )
    return queue

def job_definition(
    name,
    json,
    tags
):
    definition = aws.batch.JobDefinition(
    f"{name}-definition",
    type="container",
    platform_capabilities=["FARGATE"],
    container_properties=json
    )
    return definition
