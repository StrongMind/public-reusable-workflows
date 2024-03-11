import json
from typing import Mapping, Optional, Dict
from unittest.mock import Base

from strongmind_deployment.util import get_project_stack, get_project_stack_name
import pulumi
import pulumi_aws as aws
import pulumi_aws.ecs as ecs
import pulumi_awsx as awsx
import pulumi_awsx.ecs as ecsx
from pulumi_awsx.awsx import DefaultRoleWithPolicyArgs
from strongmind_deployment.vpc import VpcComponent

class EcsComponentArgs:
    def __init__(
        self,
        vpc_id: pulumi.Output[str],
        container_image: pulumi.Output[str],
        target_group: Optional[aws.lb.TargetGroup] = None,
        env_vars: Dict[str, str] = None,
        health_check_path: Optional[str] = "/up",
        desired_count: Optional[int] = 1,
        container_port: int = 80,
        cluster_name: str = None,
        cpu: Optional[str] = None,
        memory: Optional[str] = None,
        entry_point: Optional[str] = None,
        command: Optional[str] = None,
        secrets: Optional[Mapping[str, pulumi.Input[str]]] = None,
    ) -> None:
        self.vpc_id = vpc_id
        self.cluster_name = cluster_name or f"{get_project_stack_name('cluster')}"
        self.container_image = container_image
        self.target_group = target_group
        self.container_port = container_port
        self.env_vars = env_vars
        self.health_check_path = health_check_path
        self.desired_count = desired_count
        self.cpu = cpu
        self.memory = memory
        self.entry_point = entry_point
        self.command = command
        self.secrets = secrets

class EcsComponent(pulumi.ComponentResource):
    """
    This component originated from the container.py ContainerComponent class.
    """

    # TODO: move to @properties to define the public interface?
    # we want to make it clear which is Open/Closed to this class.
    cluster: ecs.Cluster

    def __init__(self, name, args: EcsComponentArgs, opts=None) -> None:
        super().__init__('strongmind:global_build:commons:clustered_container_service', name, None, opts)
        self.name = name
        self.args = args
        self.project_stack_name = get_project_stack_name(name)
        self.create_resources()

    def create_resources(self) -> None:

        self.env_vars = self.dict_to_named_env_vars() if self.args.env_vars else None
        self.log_group = self.create_log_group()
        # # iam
        self.execution_role = self.create_execution_role()
        self.task_role = self.create_task_role()

        # ecs
        self.cluster = self.create_cluster()
        self.create_service(target_group=self.args.target_group, cluster=self.cluster)

    # TODO: candidate for common function
    def dict_to_named_env_vars(self):
        return [{"name": k, "value": v} for k, v in self.args.env_vars.items()]

    def create_log_group(self) -> aws.cloudwatch.LogGroup:
        # TODO: use a logs component for this - this was done as a quick refactor.

        log_name = 'log'
        if self.name != 'container':
            log_name = f'{self.name}-log'

        return aws.cloudwatch.LogGroup(
                  log_name,
                  retention_in_days=14,
                  name=f'/aws/ecs/{get_project_stack()}',
                #   tags=self.tags
              )

    def create_cluster(self) -> aws.ecs.Cluster:
        cluster_name = f"{self.project_stack_name}-cluster"
        cluster = aws.ecs.Cluster(
            cluster_name,
            name=cluster_name,
            # tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )
        return cluster

    def create_execution_role(self) -> aws.iam.Role:
        """
        The default execution role which is public, for modification.
        """
        resource_name = f"{self.project_stack_name}-execution-role"
        execution_role = aws.iam.Role(
            resource_name, 
            name=resource_name,
            assume_role_policy=json.dumps(
                {
                    "Version": "2008-10-17",
                    "Statement": [
                        {
                            "Sid": "",
                            "Effect": "Allow",
                            "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                            "Action": "sts:AssumeRole",
                        }
                    ],
                }
            ),
            # tags=self.args.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )
        
        policy_name = f"{self.project_stack_name}-execution-policy"
        aws.iam.RolePolicy(
            policy_name,
            name=policy_name,
            role=execution_role.id,
            policy=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Action": [
                                "ecs:*",
                                "ecr:GetAuthorizationToken",
                                "ecr:BatchCheckLayerAvailability",
                                "ecr:GetDownloadUrlForLayer",
                                "ecr:BatchGetImage",
                                "ecr:GetRepositoryPolicy",
                                "ecr:DescribeRepositories",
                                "ecr:ListImages",
                                "ecr:DescribeImages",
                                "ecr:InitiateLayerUpload",
                                "ecr:UploadLayerPart",
                                "ecr:CompleteLayerUpload",
                                "ecr:PutImage",
                                "logs:CreateLogStream",
                                "logs:PutLogEvents",
                                "secretsmanager:GetSecretValue",
                            ],
                            "Effect": "Allow",
                            "Resource": "*",
                        }
                    ],
                }
            ),
            opts=pulumi.ResourceOptions(parent=self),
        )

        return execution_role

    def create_task_role(self) -> aws.iam.Role:
        task_role_name = f"{self.project_stack_name}-task-role"
        task_role = aws.iam.Role(
            task_role_name,
            name=task_role_name,
            assume_role_policy=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Sid": "",
                            "Effect": "Allow",
                            "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                            "Action": "sts:AssumeRole",
                        }
                    ],
                }
            ),
            # tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # TODO: extract this as a named policy in a common policy lib area.
        task_policy_name = f"{self.project_stack_name}-task-policy"
        aws.iam.RolePolicy(
            task_policy_name,
            name=task_policy_name,
            role=task_role.id,
            policy=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Action": [
                                "ssmmessages:CreateControlChannel",
                                "ssmmessages:CreateDataChannel",
                                "ssmmessages:OpenControlChannel",
                                "ssmmessages:OpenDataChannel"
                            ],
                            "Effect": "Allow",
                            "Resource": "*",
                        }
                    ],
                }
            ),
            opts=pulumi.ResourceOptions(parent=self),
        )

        return task_role

    def create_service(
        self,
        cluster: ecs.Cluster,
        log_group: aws.cloudwatch.LogGroup,
        target_group: aws.lb.TargetGroup = None
    ) -> ecsx.FargateService:
        """
        Optionally accepts a target group. 
        If not supplied, the service will not have inbound network connectivity.
        """
        
        port_mappings = None
        if(target_group is not None):
            port_mappings = [
                awsx.ecs.TaskDefinitionPortMappingArgs(
                    container_port=self.args.container_port,
                    host_port=self.args.container_port,
                    target_group=target_group,
                )
            ]

        task_definition_args = awsx.ecs.FargateServiceTaskDefinitionArgs(
            execution_role=DefaultRoleWithPolicyArgs(role_arn=self.execution_role.arn),
            task_role=DefaultRoleWithPolicyArgs(role_arn=self.task_role.arn),
            skip_destroy=True,
            family=self.project_stack_name,
            container=awsx.ecs.TaskDefinitionContainerDefinitionArgs(
                name=self.project_stack_name,
                log_configuration=awsx.ecs.TaskDefinitionLogConfigurationArgs(
                    log_driver="awslogs",
                    options={
                        "awslogs-group": log_group.name,
                        "awslogs-region": "us-west-2",
                        "awslogs-stream-prefix": "container",
                    },
                ),
                image=self.args.container_image,
                cpu=self.args.cpu,
                memory=self.args.memory,
                entry_point=self.args.entry_point,
                command=self.args.command,
                essential=True,
                port_mappings=port_mappings,
                secrets=self.args.secrets,
                environment=self.env_vars,
            ),
        )
        # This uses the naming logic of the container.py, consider revising to 
        # match the pattern here.
        service_name = "service"
        if self.name != "container":
            service_name = f"{self.name}-service"

        default_task_security_group = aws.ec2.SecurityGroup(
            "securityGroup",
            vpc_id=self.args.vpc_id,
            egress=[
                aws.ec2.SecurityGroupEgressArgs(
                    from_port=0,
                    to_port=0,
                    protocol="-1",
                    cidr_blocks=["0.0.0.0/0"],
                    ipv6_cidr_blocks=["::/0"],
                )
            ],
        )

        private_subnet_ids_output = VpcComponent.get_private_subnet_ids(self.args.vpc_id)
        
        self.fargate_service = awsx.ecs.FargateService(
            service_name,
            name=self.project_stack_name,
            desired_count=self.args.desired_count,
            cluster=cluster.arn,
            continue_before_steady_state=True,
            # TODO: this logic should be sorted once the ALB is refactored.
            # health_check_grace_period_seconds=600 if self.need_load_balancer else None,
            health_check_grace_period_seconds=None,
            propagate_tags="SERVICE",
            enable_execute_command=True,
            task_definition_args=task_definition_args,
            network_configuration=aws.ecs.ServiceNetworkConfigurationArgs(
                subnets=private_subnet_ids_output.ids,
                security_groups=[default_task_security_group.id],
            ),
            # tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )
