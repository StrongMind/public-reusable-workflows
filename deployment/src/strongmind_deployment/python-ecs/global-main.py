import pulumi
import pulumi_aws
import vpc
import iam
import batch
import ecs
import cloudwatch
import os

##Global variables
stack = pulumi.get_stack()
region = pulumi_aws.config.region
config = pulumi.Config()
tags = config.require_object("tags")


###START of VPC
cidr = config.require("cidr")
vpc_object = vpc.vpc(stack, cidr, tags)
security_group_config = config.require_object("security_group")
security_group_ids = list()

for sec_g in security_group_config:
    security_group_ids.append(vpc.sg(
        stack,
        int(sec_g["from_port"]),
        int(sec_g["to_port"]),
        "tcp",
        "0.0.0.0/0",
        vpc_object.id,
        tags
    ).id)

internet_gateway = vpc.create_gateway(stack, vpc_object.id, tags)

route = vpc.create_route(
    stack,
    vpc_object.main_route_table_id,
    internet_gateway.id
)

subnet_ids=list()

subnet_dict = config.require_object("subnets")

for sub in subnet_dict:
    build_subnet = vpc.subnet(
        f"{stack}-{sub['availability_zone']}",
        vpc_object.id,
        sub["cidr_block"],
        sub["availability_zone"],
        tags
        )
    subnet_ids.append(build_subnet.id)

assume_role_policy = config.require_object("assume_role_policy")
role_policy = config.require_object("role_policy")

ecs.create_endpoints(
    stack,
    vpc_object,
    subnet_ids,
    security_group_ids,
    tags
    )

###END of VPC

###START of IAM
role = iam.create_iam_role_with_policy(
    stack,
    assume_role_policy,
    role_policy,
    tags
)
###END of iam

###START of batch setup
compute = config.require_object("compute")
image_dict = config.require_object("image")
our_image = f"{image_dict['repository_url']}:{os.environ.get('GITHUB_SHA')}"

batch_compute = batch.create_compute_environment(
    stack,
    compute["max_vcpus"],
    security_group_ids,
    subnet_ids,
    our_image,
    tags,
    role.arn
    )

batch_queue = batch.job_queue(
    stack,
    batch_compute.arn,
    compute["priority"],
    tags
)

aws_cloudwatch_log_group = cloudwatch.create_log_group(stack, "batch", "batch", tags)

service_role = role.arn
definitions = config.require_object("definition")

for define in definitions:
    memory = define["resourceRequirements"]["memory"]
    vcpu = define["resourceRequirements"]["vcpu"]
    container_name = f"{stack}-{define['name']}"
    command = define["command"]
    ASSET_BUCKET=define["ASSET_BUCKET"]
    NODE_ENV=define["NODE_ENV"]
    STAGE=define["STAGE"]
    SNOWFLAKE_U = config.require("SNOWFLAKE_USER")
    SNOWFLAKE_PASS = config.require("SNOWFLAKE_PASS")

    Our_json_output = pulumi.Output.concat(
        '{"command":[ "python","main.py" ]',
        ',"workdir":"/app"',
        ',"image":"', our_image, '"',
        ',"executionRoleArn":"', service_role,'"',
        ',"jobRoleArn":"', service_role,'"',
        ',"environment":[',
        '{"name": "NODE_ENV", "value":"', NODE_ENV, '"}'
        ',{"name": "STAGE", "value":"', STAGE, '"}'
        ',{"name": "SNOWFLAKE_USER", "value":"', SNOWFLAKE_U, '"}'
        ',{"name": "SNOWFLAKE_PASSWORD", "value":"', SNOWFLAKE_PASS, '"}'
        '],"resourceRequirements":[',
        '{"type": "MEMORY", "value":"', str(memory),'"}'
        ',{"type": "VCPU", "value":"', str(vcpu),'"}'
        '],"fargatePlatformConfiguration":',
        '{"platformVersion":"LATEST"}',
        ',"networkConfiguration":'
        '{"assignPublicIp": "ENABLED"}',
        ',"logConfiguration":',
        '{"logDriver": "awslogs","options": {"awslogs-group":"',
        aws_cloudwatch_log_group.id,
        '","awslogs-region":"',
        region,
        '","awslogs-stream-prefix": "ecs"}}'
        '}'
        )


    definition=batch.job_definition(
        stack,
        Our_json_output,
        tags
    )
###END of batch setup

###START of event bridge
environment = tags["environment"]
if environment == "prod":
    schedule_expression=config.require("event_schedule")
    eventrule = cloudwatch.create_eventrule(
        stack,
        True,
        schedule_expression,
        tags
        )

    eventtarget = cloudwatch.create_event_target(
        stack,
        batch_queue,
        eventrule.name,
        definition.arn,
        definition.name,
        role.arn
        )

###END of event bridge
