import json
import os
import re
import subprocess

import pulumi
import pulumi_aws as aws
import pulumi_awsx as awsx
from pulumi import Config, export, Output
from pulumi_awsx.awsx import DefaultRoleWithPolicyArgs
from pulumi_cloudflare import get_zone, Record

from strongmind_deployment import alb
from strongmind_deployment.autoscale import WorkerAutoscaleComponent
from strongmind_deployment.util import create_ecs_cluster

class ContainerComponent(pulumi.ComponentResource):
    def __init__(self, name, opts=None, **kwargs):
        """
        Resource that produces a containerized application running on AWS Fargate.

        :param name: The _unique_ name of the resource.
        :param opts: A bag of optional settings that control this resource's behavior.
        :key need_load_balancer: Whether to create a load balancer for the container. Defaults to True.
        :key container_image: The Docker image to use for the container. Required.
        :key container_port: The port to expose on the container. Defaults to 3000.
        :key env_vars: A dictionary of environment variables to pass to the Rails application.
        :key entry_point: The entry point for the container.
        :key command: The command to run when the container starts.
        :key cpu: The number of CPU units to reserve for the container. Defaults to 512.
        :key memory: The amount of memory (in MiB) to allow the web container to use. Defaults to 1028.
        :key secrets: A list of secrets to pass to the container. Each secret is a dictionary with the following keys:
        - name: The name of the secret.
        - value_from: The ARN of the secret.
        :key custom_health_check_path: The path to use for the health check. Defaults to `/up`.
        """
        super().__init__('strongmind:global_build:commons:container', name, None, opts)
        stack = pulumi.get_stack()

        self.alb = None
        self.autoscaling_out_alarm = None
        self.log_metric_filters = []
        self.target_group = None
        self.load_balancer_listener_redirect_http_to_https = None
        self.load_balancer_listener = None
        self.load_balancer = None
        self.cert_validation_cert = None
        self.cert_validation_record = None
        self.cert = None
        self._security_group_name = None
        self.cname_record = None
        self.need_load_balancer = kwargs.get('need_load_balancer', True)
        self.container_image = kwargs.get('container_image')
        self.container_port = kwargs.get('container_port', 3000)
        self.cpu = kwargs.get('cpu', 512)
        self.memory = kwargs.get("memory", 1028)
        self.entry_point = kwargs.get('entry_point')
        self.command = kwargs.get('command')
        self.env_vars = kwargs.get('env_vars', {})
        self.secrets = kwargs.get('secrets', [])
        self.kwargs = kwargs
        self.env_name = os.environ.get('ENVIRONMENT_NAME', 'stage')
        self.autoscaling_target = None
        self.autoscaling_out_policy = None
        self.desired_count = kwargs.get('desired_count', 2)
        self.max_capacity = 100
        self.min_capacity = self.desired_count
        self.sns_topic_arn = kwargs.get('sns_topic_arn', 'arn:aws:sns:us-west-2:221871915463:DevOps-Opsgenie')

        if stack.lower() == 'stage':
            self.sns_topic_arn = 'arn:aws:sns:us-west-2:221871915463:DevOps-Opsgenie-Stage'

        project = pulumi.get_project()
        self.project_stack = f"{project}-{stack}"
        if name != 'container':
            self.project_stack = f"{self.project_stack}-{name}"

        # Execute the command and decode the byte string to a normal string
        path = subprocess.check_output(['git', 'rev-parse', '--show-toplevel']).decode('utf-8').strip()
        file_path = f"{path}/CODEOWNERS"
        with open(file_path, 'r') as file:
            owning_team = [line.strip().split('@')[-1] for line in file if '@' in line][-1].split('/')[1]

        self.tags = {
            "product": project,
            "repository": project,
            "service": project,
            "environment": self.env_name,
            "owner": owning_team,
        }
        self.ecs_cluster_arn = kwargs.get('ecs_cluster_arn')
        if self.ecs_cluster_arn is None:
            self.ecs_cluster = create_ecs_cluster(self, self.project_stack)

            self.ecs_cluster_arn = self.ecs_cluster.arn

        if self.need_load_balancer:
            self.setup_load_balancer(kwargs, project, self.project_stack, stack)

        log_name = 'log'
        if name != 'container':
            log_name = f'{name}-log'
        self.logs = aws.cloudwatch.LogGroup(
            log_name,
            retention_in_days=14,
            name=f'/aws/ecs/{self.project_stack}',
            tags=self.tags
        )
        self.log_metric_filter_definitions = kwargs.get('log_metric_filters', [])
        for log_metric_filter in self.log_metric_filter_definitions:
            self.log_metric_filters.append(
                aws.cloudwatch.LogMetricFilter(
                    log_metric_filter["metric_transformation"]["name"],
                    name=self.project_stack + "-" + log_metric_filter["metric_transformation"]["name"],
                    log_group_name=self.logs.name,
                    pattern=log_metric_filter["pattern"],
                    metric_transformation=aws.cloudwatch.LogMetricFilterMetricTransformationArgs(
                        name=self.project_stack + "-" + log_metric_filter["metric_transformation"]["name"],
                        value=log_metric_filter["metric_transformation"]["value"],
                        namespace=log_metric_filter["metric_transformation"]["namespace"],
                        unit="Count"
                    )
                )
            )

        port_mappings = None
        if self.target_group is not None:
            port_mappings = [awsx.ecs.TaskDefinitionPortMappingArgs(
                container_port=self.container_port,
                host_port=self.container_port,
                target_group=self.target_group,
            )]

        self.execution_role = aws.iam.Role(
            f"{self.project_stack}-execution-role",
            name=f"{self.project_stack}-execution-role",
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
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )
        self.execution_policy = aws.iam.RolePolicy(
            f"{self.project_stack}-execution-policy",
            name=f"{self.project_stack}-execution-policy",
            role=self.execution_role.id,
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
        self.task_role = aws.iam.Role(
            f"{self.project_stack}-task-role",
            name=f"{self.project_stack}-task-role",
            assume_role_policy=json.dumps(
                {
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
                }
            ),
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )
        self.task_policy = aws.iam.RolePolicy(
            f"{self.project_stack}-task-policy",
            name=f"{self.project_stack}-task-policy",
            role=self.task_role.id,
            policy=json.dumps(
                {
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
                }
            ),
            opts=pulumi.ResourceOptions(parent=self),
        )

        if self.kwargs.get('storage', False):
            self.s3_policy = aws.iam.Policy(
                f"{self.project_stack}-s3-policy",
                name=f"{self.project_stack}-s3Policy",
                policy=json.dumps({
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
                tags=self.tags
                )

            self.s3_policy_attachement = aws.iam.RolePolicyAttachment(
                f"{self.project_stack}-s3PolicyAttachment",
                role=self.task_role.id,
                policy_arn=self.s3_policy.arn,
            )  

        self.task_definition_args = awsx.ecs.FargateServiceTaskDefinitionArgs(
            execution_role=DefaultRoleWithPolicyArgs(role_arn=self.execution_role.arn),
            task_role=DefaultRoleWithPolicyArgs(role_arn=self.task_role.arn),
            skip_destroy=True,
            family=self.project_stack,
            container=awsx.ecs.TaskDefinitionContainerDefinitionArgs(
                name=self.project_stack,
                log_configuration=awsx.ecs.TaskDefinitionLogConfigurationArgs(
                    log_driver="awslogs",
                    options={
                        "awslogs-group": self.logs.name,
                        "awslogs-region": "us-west-2",
                        "awslogs-stream-prefix": "container",
                    },
                ),
                image=self.container_image,
                cpu=self.cpu,
                memory=self.memory,
                entry_point=self.entry_point,
                command=self.command,
                essential=True,
                port_mappings=port_mappings,
                secrets=self.secrets,
                environment=[{"name": k, "value": v} for k, v in self.env_vars.items()]
            )
        )
        service_name = 'service'
        if name != 'container':
            service_name = f'{name}-service'
        self.fargate_service = awsx.ecs.FargateService(
            service_name,
            name=self.project_stack,
            desired_count=self.desired_count,
            cluster=self.ecs_cluster_arn,
            continue_before_steady_state=True,
            assign_public_ip=True,
            health_check_grace_period_seconds=600 if self.need_load_balancer else None,
            propagate_tags="SERVICE",
            enable_execute_command=True,
            task_definition_args=self.task_definition_args,
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        if self.kwargs.get('autoscaling'):
            self.autoscaling()
        if self.kwargs.get('worker_autoscaling'):
            pulumi.log.info("WORKER AUTOSCALING ENABLED")
            self.worker_autoscaling = WorkerAutoscaleComponent("worker-autoscale",
                                                               opts=pulumi.ResourceOptions(
                                                                   parent=self,
                                                                   depends_on=[self.fargate_service]
                                                               ),
                                                               **self.kwargs)



        self.register_outputs({})

    def autoscaling(self):

        self.autoscaling_target = aws.appautoscaling.Target(
            "autoscaling_target",
            max_capacity=self.max_capacity,
            min_capacity=self.desired_count,
            resource_id=f"service/{self.project_stack}/{self.project_stack}",
            scalable_dimension="ecs:service:DesiredCount",
            service_namespace="ecs",
            opts=pulumi.ResourceOptions(
                depends_on=[self.fargate_service]
            ),
        )
        self.autoscaling_out_policy = aws.appautoscaling.Policy(
            "autoscaling_out_policy",
            name=f"{self.project_stack}-autoscaling-out-policy",
            policy_type="StepScaling",
            resource_id=self.autoscaling_target.resource_id,
            scalable_dimension=self.autoscaling_target.scalable_dimension,
            service_namespace=self.autoscaling_target.service_namespace,
            step_scaling_policy_configuration=aws.appautoscaling.PolicyStepScalingPolicyConfigurationArgs(
                adjustment_type="ChangeInCapacity",
                cooldown=15,
                metric_aggregation_type="Maximum",
                step_adjustments=[
                    aws.appautoscaling.PolicyStepScalingPolicyConfigurationStepAdjustmentArgs(
                        metric_interval_upper_bound="10",
                        metric_interval_lower_bound="0",
                        scaling_adjustment=1,
                    ),
                    aws.appautoscaling.PolicyStepScalingPolicyConfigurationStepAdjustmentArgs(
                        metric_interval_lower_bound="10",
                        scaling_adjustment=3,
                    )
                ],
            )
        )
        self.autoscaling_out_alarm = aws.cloudwatch.MetricAlarm(
            "autoscaling_alarm",
            name=f"{self.project_stack}-auto-scaling-out-alarm",
            comparison_operator="GreaterThanOrEqualToThreshold",
            actions_enabled=True,
            alarm_actions=[self.autoscaling_out_policy.arn],
            evaluation_periods=1,
            datapoints_to_alarm=1,
            threshold=50,
            treat_missing_data="missing",
            metric_queries=[
                aws.cloudwatch.MetricAlarmMetricQueryArgs(
                    id="e1",
                    label="Expression1",
                    return_data=True,
                    expression="100*(m1/m2)",
                ),
                aws.cloudwatch.MetricAlarmMetricQueryArgs(
                    id="m1",
                    return_data=False,
                    metric=aws.cloudwatch.MetricAlarmMetricQueryMetricArgs(
                        namespace="ECS/ContainerInsights",
                        metric_name="CpuUtilized",
                        dimensions={
                            "ClusterName": self.project_stack,
                            "ServiceName": self.project_stack
                        },
                        period=60,
                        stat="p99",
                    ),
                ),
                aws.cloudwatch.MetricAlarmMetricQueryArgs(
                    id="m2",
                    return_data=False,
                    metric=aws.cloudwatch.MetricAlarmMetricQueryMetricArgs(
                        namespace="ECS/ContainerInsights",
                        metric_name="CpuReserved",
                        dimensions={
                            "ServiceName": self.project_stack,
                            "ClusterName": self.project_stack,
                        },
                        period=60,
                        stat="p99",
                    ),
                )
            ],
        )
        self.autoscaling_in_policy = aws.appautoscaling.Policy(
            "autoscaling_in_policy",
            name=f"{self.project_stack}-autoscaling-in-policy",
            policy_type="StepScaling",
            resource_id=self.autoscaling_target.resource_id,
            scalable_dimension=self.autoscaling_target.scalable_dimension,
            service_namespace=self.autoscaling_target.service_namespace,
            step_scaling_policy_configuration=aws.appautoscaling.PolicyStepScalingPolicyConfigurationArgs(
                adjustment_type="ChangeInCapacity",
                cooldown=900,
                metric_aggregation_type="Maximum",
                step_adjustments=[
                    aws.appautoscaling.PolicyStepScalingPolicyConfigurationStepAdjustmentArgs(
                        metric_interval_upper_bound="0",
                        scaling_adjustment=-1,
                    )
                ],
            )
        )
        self.autoscaling_in_alarm = aws.cloudwatch.MetricAlarm(
            "autoscaling_in_alarm",
            name=f"{self.project_stack}-auto-scaling-in-alarm",
            comparison_operator="LessThanOrEqualToThreshold",
            actions_enabled=True,
            alarm_actions=[self.autoscaling_in_policy.arn],
            evaluation_periods=5,
            datapoints_to_alarm=1,
            threshold=35,
            treat_missing_data="missing",
            metric_queries=[
                aws.cloudwatch.MetricAlarmMetricQueryArgs(
                    id="e1",
                    label="Expression1",
                    return_data=True,
                    expression="100*(m1/m2)",
                ),
                aws.cloudwatch.MetricAlarmMetricQueryArgs(
                    id="m1",
                    return_data=False,
                    metric=aws.cloudwatch.MetricAlarmMetricQueryMetricArgs(
                        namespace="ECS/ContainerInsights",
                        metric_name="CpuUtilized",
                        dimensions={
                            "ClusterName": self.project_stack,
                            "ServiceName": self.project_stack
                        },
                        period=60,
                        stat="p99",
                    ),
                ),
                aws.cloudwatch.MetricAlarmMetricQueryArgs(
                    id="m2",
                    return_data=False,
                    metric=aws.cloudwatch.MetricAlarmMetricQueryMetricArgs(
                        namespace="ECS/ContainerInsights",
                        metric_name="CpuReserved",
                        dimensions={
                            "ServiceName": self.project_stack,
                            "ClusterName": self.project_stack,
                        },
                        period=60,
                        stat="p99",
                    ),
                ),
            ],
        )

    def setup_load_balancer(self, kwargs, project, project_stack, stack):
        self.certificate(project, stack)

        default_vpc = awsx.ec2.DefaultVpc("default_vpc")
        health_check_path = kwargs.get('custom_health_check_path', '/up')

        self.target_group = aws.lb.TargetGroup(
            "target_group",
            name=f"{project_stack}-tg",
            port=self.container_port,
            protocol="HTTP",
            target_type="ip",
            vpc_id=default_vpc.vpc_id,
            health_check=aws.lb.TargetGroupHealthCheckArgs(
                enabled=True,
                path=health_check_path,
                port=str(self.container_port),
                protocol="HTTP",
                matcher="200",
                interval=30,
                timeout=5,
                healthy_threshold=5,
                unhealthy_threshold=2,
            ),
        )

        alb_args = alb.AlbArgs(
            vpc_id=default_vpc.vpc_id,
            subnets=default_vpc.public_subnet_ids,
            placement=alb.AlbPlacement.EXTERNAL,
            certificate_arn=self.cert.arn,
        )
        self.alb = alb.Alb("loadbalancer", alb_args)
        self.load_balancer = self.alb.alb
        self.load_balancer_listener = self.alb.https_listener
        self.load_balancer_listener_redirect_http_to_https = self.alb.redirect_listener

        self.listener_rule = aws.lb.ListenerRule(
            "service_listener_rule",
            listener_arn=self.alb.https_listener.arn,
            priority=1000,
            actions=[
                aws.lb.ListenerRuleActionArgs(
                    type="forward", target_group_arn=self.target_group.arn
                )
            ],
            conditions=[
                aws.lb.ListenerRuleConditionArgs(
                    path_pattern=aws.lb.ListenerRuleConditionPathPatternArgs(
                        values=["/*"]
                    )
                )
            ],
        )


        load_balancer_dimension = self.load_balancer.arn.apply(
            lambda arn: arn.split("/")[-1]
        )
        target_group_dimension = self.target_group.arn.apply(
            lambda arn: arn.split("/")[-1]
        )
        self.healthy_host_metric_alarm = pulumi.Output.all(load_balancer_dimension, target_group_dimension).apply(lambda args: 
            aws.cloudwatch.MetricAlarm(
                "healthy_host_metric_alarm",
                name=f"{project_stack}-healthy-host-metric-alarm",
                comparison_operator="LessThanThreshold",
                datapoints_to_alarm=1,
                dimensions={
                    "LoadBalancer":f"app/{project_stack}/{args[0]}",
                    "TargetGroup":f"targetgroup/{project_stack}/{args[1]}",
                },
                evaluation_periods=1,
                metric_name="HealthyHostCount",
                namespace="AWS/ApplicationELB",
                alarm_actions=[self.sns_topic_arn],
                ok_actions=[self.sns_topic_arn],
                period=60,
                statistic="Maximum",
                threshold=self.desired_count,
                treat_missing_data="notBreaching",
                tags=self.tags,
            )
        )

        self.dns(project, stack)

    def certificate(self, name, stack):
        if stack != "prod":
            name = f"{stack}-{name}"
        domain = 'strongmind.com'
        full_name = f"{name}.{domain}"
        self.cert = aws.acm.Certificate(
            "cert",
            domain_name=full_name,
            validation_method="DNS",
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

    def dns(self, name, stack):
        if stack != "prod":
            name = f"{stack}-{name}"
        domain = 'strongmind.com'
        full_name = f"{name}.{domain}"
        zone_id = self.kwargs.get('zone_id', 'b4b7fec0d0aacbd55c5a259d1e64fff5')
        lb_dns_name = self.kwargs.get('load_balancer_dns_name',
                                      self.load_balancer.dns_name)  # pragma: no cover
        if self.kwargs.get('cname', True):
            self.cname_record = Record(
                'cname_record',
                name=name,
                type='CNAME',
                allow_overwrite=True,
                zone_id=zone_id,
                content=lb_dns_name,
                ttl=1,
                opts=pulumi.ResourceOptions(parent=self),
            )
        pulumi.export("url", Output.concat("https://", full_name))

        domain_validation_options = self.kwargs.get('domain_validation_options',
                                                    self.cert.domain_validation_options)  # pragma: no cover

        resource_record_value = domain_validation_options[0].resource_record_value

        def remove_trailing_period(value):
            return re.sub("\\.$", "", value)

        if type(resource_record_value) != str:
            resource_record_value = resource_record_value.apply(remove_trailing_period)

        self.cert_validation_record = Record(
            'cert_validation_record',
            name=domain_validation_options[0].resource_record_name,
            type=domain_validation_options[0].resource_record_type,
            zone_id=zone_id,
            content=resource_record_value,
            ttl=1,
            opts=pulumi.ResourceOptions(parent=self, depends_on=[self.cert]),
        )

        self.cert_validation_cert = aws.acm.CertificateValidation(
            "cert_validation",
            certificate_arn=self.cert.arn,
            validation_record_fqdns=[self.cert_validation_record.hostname],
            opts=pulumi.ResourceOptions(parent=self, depends_on=[self.cert_validation_record]),
        )
