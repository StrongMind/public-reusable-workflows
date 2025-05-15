import json
import os
import re
import subprocess
from datetime import datetime, timezone, timedelta

import pulumi
import pulumi_aws as aws
import pulumi_awsx as awsx
from pulumi import Output
from pulumi_awsx.awsx import DefaultRoleWithPolicyArgs
from pulumi_cloudflare import Record

from strongmind_deployment import alb
from strongmind_deployment import operations
from strongmind_deployment.util import create_ecs_cluster, qualify_component_name
from strongmind_deployment.worker_autoscale import WorkerAutoscaleComponent


class ContainerComponent(pulumi.ComponentResource):
    def __init__(self, name, opts=None, **kwargs):
        """
        Resource that produces a containerized application running on AWS Fargate.

        :param name: The _unique_ name of the resource.
        :param opts: A bag of optional settings that control this resource's behavior.
        :key namespace: A name to override the default naming of resources and DNS names.
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
        :key autoscale_threshold The amount of allowable TargetResponseTime before we scale.
        :key use_cloudfront: Whether to create a CloudFront distribution in front of the ALB. Defaults to False.
        :key scheduled_scaling: Whether to enable time-based scaling. Defaults to False.
        :key pre_scale_time: MST time to start peak hours (format: "HH:MM"). Required if scheduled_scaling is True.
        :key post_scale_time: MST time to end peak hours (format: "HH:MM"). Required if scheduled_scaling is True.
        :key peak_min_capacity: Minimum capacity during peak hours. Required if scheduled_scaling is True.
        :key desired_web_count: Minimum capacity during off-peak hours. Defaults to 2.
        :key additional_domain_aliases: Optional list of additional domain names to be included in the CloudFront distribution's 
                                      certificate and aliases. Each domain should be a full domain name 
                                      (e.g., ["enrollment.strongmind.com"]). These domains will be added to the certificate's 
                                      SAN and the CloudFront distribution's aliases.
        """
        super().__init__('strongmind:global_build:commons:container', name, None, opts)
        stack = pulumi.get_stack()

        self.alb = None
        self.autoscaling_out_alarm = None
        self.log_metric_filters = []
        self.target_group = None
        self.load_balancer = None
        self.load_balancer_listener_redirect_http_to_https = None
        self.load_balancer_listener = None
        self.cert_validation_cert = None
        self.cert_validation_record = None
        self.cert = None
        self._security_group_name = None
        self.cname_record = None
        self.worker_autoscaling = None
        self.ecs_cluster = kwargs.get('ecs_cluster')
        self.need_load_balancer = kwargs.get('need_load_balancer', True)
        self.container_image = kwargs.get('container_image')
        self.container_port = kwargs.get('container_port', 3000)
        self.cpu = kwargs.get('cpu', 2048)
        self.memory = kwargs.get("memory", 4096)
        self.entry_point = kwargs.get('entry_point')
        self.command = kwargs.get('command')
        self.env_vars = kwargs.get('env_vars', {})
        self.secrets = kwargs.get('secrets', [])
        self.kwargs = kwargs
        self.env_name = os.environ.get('ENVIRONMENT_NAME', 'stage')
        self.autoscaling_target = None
        self.autoscaling_out_policy = None
        self.autoscale_threshold = kwargs.get('autoscale_threshold', 5)
        self.desired_count = kwargs.get('desired_count', 2)
        self.max_capacity = 100
        self.min_capacity = kwargs.get('desired_web_count', 2)
        self.sns_topic_arn = kwargs.get('sns_topic_arn')
        self.binary_sns_topic_arn = os.environ.get('BINARY_SNS_TOPIC_ARN')
        self.strongmind_service_updates_topic_arn = os.environ.get('STRONGMIND_SERVICE_UPDATES_TOPIC_ARN')
        self.deployment_maximum_percent = kwargs.get('deployment_maximum_percent', 200)
        self.cloudfront_distribution = None
        self.scheduled_scaling = kwargs.get('scheduled_scaling', False)
        self.pre_scale_time = kwargs.get('pre_scale_time')
        self.post_scale_time = kwargs.get('post_scale_time')
        self.peak_min_capacity = kwargs.get('peak_min_capacity')

        project = pulumi.get_project()
        self.namespace = kwargs.get('namespace', f"{project}-{stack}")
        if name != 'container':
            self.namespace = f"{self.namespace}-{name}"

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

        if not self.ecs_cluster:
            self.ecs_cluster = create_ecs_cluster(self, self.namespace, self.kwargs)

        self.ecs_cluster_arn = self.ecs_cluster.arn

        if self.need_load_balancer:
            self.setup_load_balancer(kwargs, project, self.namespace, stack)

        log_name = 'log'
        if name != 'container':
            log_name = f'{name}-log'
        self.logs = aws.cloudwatch.LogGroup(
            qualify_component_name(log_name, self.kwargs),
            retention_in_days=14,
            name=f'/aws/ecs/{self.namespace}',
            tags=self.tags
        )
        self.log_metric_filter_definitions = kwargs.get('log_metric_filters', [])
        for log_metric_filter in self.log_metric_filter_definitions:
            self.log_metric_filters.append(
                aws.cloudwatch.LogMetricFilter(
                    log_metric_filter["metric_transformation"]["name"],
                    name=self.namespace + "-" + log_metric_filter["metric_transformation"]["name"],
                    log_group_name=self.logs.name,
                    pattern=log_metric_filter["pattern"],
                    metric_transformation=aws.cloudwatch.LogMetricFilterMetricTransformationArgs(
                        name=self.namespace + "-" + log_metric_filter["metric_transformation"]["name"],
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
            f"{self.namespace}-execution-role",
            name=f"{self.namespace}-execution-role",
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
            f"{self.namespace}-execution-policy",
            name=f"{self.namespace}-execution-policy",
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
            f"{self.namespace}-task-role",
            name=f"{self.namespace}-task-role",
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
            f"{self.namespace}-task-policy",
            name=f"{self.namespace}-task-policy",
            role=self.task_role.id,
            policy=json.dumps(
                {
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
                                "ses:SendRawEmail",
                            ],
                            "Effect": "Allow",
                            "Resource": "*",
                        }
                    ],
                }
            ),
            opts=pulumi.ResourceOptions(parent=self),
        )

        self.s3_policy = aws.iam.Policy(
            f"{self.namespace}-s3-policy",
            name=f"{self.namespace}-s3Policy",
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
            f"{self.namespace}-s3PolicyAttachment",
            role=self.task_role.id,
            policy_arn=self.s3_policy.arn,
        )

        self.task_definition_args = awsx.ecs.FargateServiceTaskDefinitionArgs(
            execution_role=DefaultRoleWithPolicyArgs(role_arn=self.execution_role.arn),
            task_role=DefaultRoleWithPolicyArgs(role_arn=self.task_role.arn),
            skip_destroy=True,
            family=self.namespace,
            container=awsx.ecs.TaskDefinitionContainerDefinitionArgs(
                name=self.namespace,
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
            qualify_component_name(f'{service_name}', self.kwargs),
            name=self.namespace,
            desired_count=self.desired_count,
            cluster=self.ecs_cluster_arn,
            continue_before_steady_state=True,
            assign_public_ip=True,
            health_check_grace_period_seconds=600 if self.need_load_balancer else None,
            propagate_tags="SERVICE",
            enable_execute_command=True,
            task_definition_args=self.task_definition_args,
            deployment_maximum_percent=self.deployment_maximum_percent,
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self, ignore_changes=["desired_count"]),
        )

        if self.kwargs.get('autoscale'):
            self.autoscaling()
        if self.kwargs.get('worker_autoscale'):
            self.worker_autoscaling = WorkerAutoscaleComponent(qualify_component_name("worker-autoscale", self.kwargs),
                                                               fargate_service=self.fargate_service,
                                                               opts=pulumi.ResourceOptions(
                                                                   parent=self,
                                                                   depends_on=[self.fargate_service]
                                                               ),
                                                               **self.kwargs)

        self.register_outputs({})

    def _validate_time_format(self, time_str):
        """Validate time string is in HH:MM format."""
        try:
            hour, minute = map(int, time_str.split(":"))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError
            return True
        except ValueError:
            raise ValueError("pre_scale_time must be in 'HH:MM' format (24-hour)")

    def _validate_scheduled_scaling(self):
        if not self.scheduled_scaling:
            return

        if not all([self.pre_scale_time, self.post_scale_time, self.peak_min_capacity]):
            raise ValueError("pre_scale_time, post_scale_time, and peak_min_capacity must be provided when scheduled_scaling is enabled")

        self._validate_time_format(self.pre_scale_time)
        self._validate_time_format(self.post_scale_time)
        self._validate_time_window(self.pre_scale_time, self.post_scale_time)

    def _validate_time_window(self, start_time, end_time):
        start_hour, start_minute = map(int, start_time.split(":"))
        end_hour, end_minute = map(int, end_time.split(":"))
        start_minutes = start_hour * 60 + start_minute
        end_minutes = end_hour * 60 + end_minute
        if end_minutes <= start_minutes:
            raise ValueError("post_scale_time must be after pre_scale_time")

    def _create_scheduled_scaling(self):
        if not self.scheduled_scaling or self.env_name != 'prod':
            return

        self._validate_scheduled_scaling()
        
        start_hour, start_minute = self.pre_scale_time.split(":")
        self.peak_scale_up = aws.appautoscaling.ScheduledAction(
            qualify_component_name("pre_scale_action", self.kwargs),
            name=f"{self.namespace}-pre-scale-action",
            service_namespace=self.autoscaling_target.service_namespace,
            resource_id=self.autoscaling_target.resource_id,
            scalable_dimension=self.autoscaling_target.scalable_dimension,
            schedule=f"cron(0 {start_minute} {start_hour} ? * MON-FRI)", 
            timezone="Etc/GMT+7",  # MST is UTC-7, which is Etc/GMT+7 in IANA format
            scalable_target_action=aws.appautoscaling.ScheduledActionScalableTargetActionArgs(
                min_capacity=self.peak_min_capacity,
                max_capacity=self.max_capacity
            ),
            opts=pulumi.ResourceOptions(
                parent=self,
                depends_on=[self.autoscaling_target]
            )
        )

        end_hour, end_minute = self.post_scale_time.split(":")
        self.peak_scale_down = aws.appautoscaling.ScheduledAction(
            qualify_component_name("post_scale_action", self.kwargs),
            name=f"{self.namespace}-post-scale-action",
            service_namespace=self.autoscaling_target.service_namespace,
            resource_id=self.autoscaling_target.resource_id,
            scalable_dimension=self.autoscaling_target.scalable_dimension,
            schedule=f"cron(0 {end_minute} {end_hour} ? * MON-FRI)", 
            timezone="Etc/GMT+7",  # MST is UTC-7, which is Etc/GMT+7 in IANA format
            scalable_target_action=aws.appautoscaling.ScheduledActionScalableTargetActionArgs(
                min_capacity=self.min_capacity,
                max_capacity=self.max_capacity
            ),
            opts=pulumi.ResourceOptions(
                parent=self,
                depends_on=[self.autoscaling_target, self.peak_scale_up]
            )
        )

    def autoscaling(self):

        fargate_service_id = self.fargate_service.service.id.apply(lambda x: x.split(":")[-1])

        self.autoscaling_target = aws.appautoscaling.Target(
            qualify_component_name("autoscaling_target", self.kwargs),
            max_capacity=self.max_capacity,
            min_capacity=self.min_capacity,
            resource_id=fargate_service_id,
            scalable_dimension="ecs:service:DesiredCount",
            service_namespace="ecs",
            opts=pulumi.ResourceOptions(
                parent=self,
                depends_on=[self.fargate_service]
            ),
        )
        self.autoscaling_out_policy = aws.appautoscaling.Policy(
            qualify_component_name("autoscaling_out_policy", self.kwargs),
            name=f"{self.namespace}-autoscaling-out-policy",
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
            ),
            opts=pulumi.ResourceOptions(
                parent=self,
                depends_on=[self.fargate_service]
            )
        )
        target_group_dimension = self.target_group.arn.apply(
            lambda arn: arn.split(":")[-1]
        )
        load_balancer_arn = self.load_balancer.arn.apply(
            lambda arn: arn.split("/", 1)[1]
        )
        self.autoscaling_out_alarm = aws.cloudwatch.MetricAlarm(
            qualify_component_name("autoscaling_alarm", self.kwargs),
            name=f"{self.namespace}-auto-scaling-out-alarm",
            comparison_operator="GreaterThanOrEqualToThreshold",
            actions_enabled=True,
            alarm_actions=[self.autoscaling_out_policy.arn],
            metric_name="TargetResponseTime",
            namespace="AWS/ApplicationELB",
            extended_statistic="p95",
            dimensions={
                "TargetGroup": target_group_dimension,
                "LoadBalancer": load_balancer_arn,
            },
            period=60,
            evaluation_periods=1,
            datapoints_to_alarm=1,
            threshold=self.autoscale_threshold,
            treat_missing_data="missing",
            tags=self.tags,
            opts=pulumi.ResourceOptions(
                parent=self,
                ignore_changes=["Threshold"],
                depends_on=[self.fargate_service]
            )
        )

        self.autoscaling_in_policy = aws.appautoscaling.Policy(
            qualify_component_name("autoscaling_in_policy", self.kwargs),
            name=f"{self.namespace}-autoscaling-in-policy",
            policy_type="StepScaling",
            resource_id=self.autoscaling_target.resource_id,
            scalable_dimension=self.autoscaling_target.scalable_dimension,
            service_namespace=self.autoscaling_target.service_namespace,
            step_scaling_policy_configuration=aws.appautoscaling.PolicyStepScalingPolicyConfigurationArgs(
                adjustment_type="ChangeInCapacity",
                cooldown=300,
                metric_aggregation_type="Maximum",
                step_adjustments=[
                    aws.appautoscaling.PolicyStepScalingPolicyConfigurationStepAdjustmentArgs(
                        metric_interval_upper_bound="0",
                        scaling_adjustment=-1,
                    )
                ],
            ),
            opts=pulumi.ResourceOptions(
                parent=self,
                depends_on=[self.fargate_service]
            )
        )

        self.autoscaling_in_alarm = aws.cloudwatch.MetricAlarm(
            qualify_component_name("autoscaling_in_alarm", self.kwargs),
            name=f"{self.namespace}-auto-scaling-in-alarm",
            comparison_operator="LessThanThreshold",
            actions_enabled=True,
            alarm_actions=[self.autoscaling_in_policy.arn],
            evaluation_periods=5,
            datapoints_to_alarm=1,
            threshold=self.autoscale_threshold,
            treat_missing_data="missing",
            metric_name="TargetResponseTime",
            namespace="AWS/ApplicationELB",
            extended_statistic="p95",
            dimensions={
                "TargetGroup": target_group_dimension,
                "LoadBalancer": load_balancer_arn,
            },
            period=60,
            tags=self.tags,
            opts=pulumi.ResourceOptions(
                parent=self,
                depends_on=[self.fargate_service]
            )
        )

        self.running_tasks_alarm = aws.cloudwatch.MetricAlarm(
            qualify_component_name("running_tasks_alarm", self.kwargs),
            name=f"{self.namespace}-running-tasks-alarm",
            comparison_operator="GreaterThanOrEqualToThreshold",
            evaluation_periods=1,
            metric_name="RunningTaskCount",
            namespace="ECS/ContainerInsights",
            dimensions={
                "ClusterName": self.ecs_cluster.name.apply(lambda name: name),
                "ServiceName": self.namespace
            },
            period=60,
            statistic="Maximum",
            threshold=100,
            alarm_actions=[self.sns_topic_arn, self.binary_sns_topic_arn],
            ok_actions=[self.sns_topic_arn, self.binary_sns_topic_arn],
            alarm_description="Alarm when ECS service running tasks are at Max of 100",
            tags=self.tags
        )
        pulumi.log.info(f"SCHEDULED SCALING: {self.scheduled_scaling}")
        if self.scheduled_scaling:
            self._validate_scheduled_scaling()
            self._create_scheduled_scaling()

    def setup_load_balancer(self, kwargs, project, namespace, stack):
        self.certificate(project, stack)

        default_vpc = awsx.ec2.DefaultVpc(qualify_component_name("default_vpc", self.kwargs))
        health_check_path = kwargs.get('custom_health_check_path', '/up')

        self.target_group = aws.lb.TargetGroup(
            qualify_component_name("target_group", self.kwargs, truncate=True),
            name=f"{namespace}-tg"[:32],
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
                healthy_threshold=2,
                unhealthy_threshold=2,
            ),
        )
        alb_args = alb.AlbArgs(
            vpc_id=default_vpc.vpc_id,
            subnets=default_vpc.public_subnet_ids,
            placement=alb.AlbPlacement.EXTERNAL,
            certificate_arn=self.cert.arn,
            tags=self.tags,
            namespace=self.kwargs.get('namespace', None)
        )
        self.alb = alb.Alb(qualify_component_name("loadbalancer", self.kwargs), alb_args, **self.kwargs)
        self.load_balancer = self.alb.alb
        self.load_balancer_listener = self.alb.https_listener
        self.load_balancer_listener_redirect_http_to_https = self.alb.redirect_listener

        self.listener_rule = aws.lb.ListenerRule(
            qualify_component_name("service_listener_rule", self.kwargs),
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
        target_group_name = self.target_group.name.apply(
            lambda name: name.split("/")[-1]
        )
        load_balancer_name = self.load_balancer.name.apply(
            lambda name: name.split("/")[-1]
        )

        self.unhealthy_host_metric_alarm = pulumi.Output.all(load_balancer_dimension, target_group_dimension,
                                                             load_balancer_name, target_group_name).apply(lambda args:
                                                                                                          aws.cloudwatch.MetricAlarm(
                                                                                                              qualify_component_name(
                                                                                                                  "unhealthy_host_metric_alarm",
                                                                                                                  self.kwargs),
                                                                                                              name=f"{namespace}-unhealthy-host-metric-alarm",
                                                                                                              actions_enabled=True,
                                                                                                              ok_actions=[
                                                                                                                  self.sns_topic_arn,
                                                                                                                  self.strongmind_service_updates_topic_arn],
                                                                                                              alarm_actions=[
                                                                                                                  self.sns_topic_arn,
                                                                                                                  self.strongmind_service_updates_topic_arn],
                                                                                                              insufficient_data_actions=[],
                                                                                                              evaluation_periods=1,
                                                                                                              datapoints_to_alarm=1,
                                                                                                              threshold=0.25,
                                                                                                              comparison_operator="GreaterThanThreshold",
                                                                                                              treat_missing_data="notBreaching",
                                                                                                              tags=self.tags,
                                                                                                              metric_queries=[
                                                                                                                  aws.cloudwatch.MetricAlarmMetricQueryArgs(
                                                                                                                      id="e1",
                                                                                                                      label="UnhealthyHostRatio",
                                                                                                                      return_data=True,
                                                                                                                      expression="IF(desired_tasks > 0, unhealthy_hosts / desired_tasks, 0)"
                                                                                                                  ),
                                                                                                                  aws.cloudwatch.MetricAlarmMetricQueryArgs(
                                                                                                                      id="unhealthy_hosts",
                                                                                                                      return_data=False,
                                                                                                                      metric=aws.cloudwatch.MetricAlarmMetricQueryMetricArgs(
                                                                                                                          namespace="AWS/ApplicationELB",
                                                                                                                          metric_name="UnHealthyHostCount",
                                                                                                                          dimensions={
                                                                                                                              "TargetGroup": f"targetgroup/{args[3]}/{args[1]}",
                                                                                                                              "LoadBalancer": f"app/{args[2]}/{args[0]}"
                                                                                                                          },
                                                                                                                          period=60,
                                                                                                                          stat="Maximum"
                                                                                                                      )
                                                                                                                  ),
                                                                                                                  aws.cloudwatch.MetricAlarmMetricQueryArgs(
                                                                                                                      id="desired_tasks",
                                                                                                                      return_data=False,
                                                                                                                      metric=aws.cloudwatch.MetricAlarmMetricQueryMetricArgs(
                                                                                                                          namespace="ECS/ContainerInsights",
                                                                                                                          metric_name="DesiredTaskCount",
                                                                                                                          dimensions={
                                                                                                                              "ClusterName": self.ecs_cluster.name,
                                                                                                                              "ServiceName": self.namespace
                                                                                                                          },
                                                                                                                          period=60,
                                                                                                                          stat="Maximum"
                                                                                                                      )
                                                                                                                  )
                                                                                                              ]
                                                                                                          )
                                                                                                          )

        if kwargs.get('use_cloudfront', True):
            self.setup_cloudfront(project, stack)

    def setup_cloudfront(self, project, stack):
        """Set up CloudFront distribution in front of the ALB"""
        if stack != "prod":
            name = f"{stack}-{project}"
            cdn_bucket = "strongmind-cdn-stage"
        else:
            name = project
            cdn_bucket = "strongmind-cdn-prod"

        name = self.kwargs.get('namespace', name)
        domain = 'strongmind.com'
        full_name = f"{name}.{domain}"

        aws_east_1 = aws.Provider(qualify_component_name("aws-east-1", self.kwargs), region="us-east-1")

        # Get additional domain aliases
        additional_domains = self.kwargs.get('additional_domain_aliases', [])

        self.cloudfront_cert = aws.acm.Certificate(
            qualify_component_name("cloudfront-cert", self.kwargs),
            domain_name=full_name,
            subject_alternative_names=additional_domains if additional_domains else None,
            validation_method="DNS",
            tags=self.tags,
            opts=pulumi.ResourceOptions(
                provider=aws_east_1,
            )
        )

        domain_validation_options = self.cloudfront_cert.domain_validation_options
        zone_id = self.kwargs.get('zone_id', 'b4b7fec0d0aacbd55c5a259d1e64fff5')

        def remove_trailing_period(value):
            return re.sub("\\.$", "", value)

        # Create validation records for all domains
        def create_validation_records(validation_options):
            records = []
            for i, option in enumerate(validation_options):
                # Keep original resource name for primary domain to maintain existing resources
                if option['domain_name'] == full_name:
                    record_name = "cert_validation_record"
                else:
                    # Only create new records for additional domains
                    record_name = f"cert_validation_record_{option['domain_name'].replace('.', '_')}"

                records.append(Record(
                    qualify_component_name(record_name, self.kwargs),
                    name=option['resource_record_name'],
                    type=option['resource_record_type'],
                    zone_id=zone_id,
                    content=remove_trailing_period(option['resource_record_value']),
                    ttl=1,
                    opts=pulumi.ResourceOptions(
                        parent=self,
                        depends_on=[self.cloudfront_cert]
                    )
                ))
            return records

        self.cloudfront_cert_validation_records = domain_validation_options.apply(create_validation_records)

        # Ensure certificate validation completes before creating distribution
        self.cloudfront_cert_validation = aws.acm.CertificateValidation(
            qualify_component_name("cert_validation", self.kwargs),
            certificate_arn=self.cloudfront_cert.arn,
            validation_record_fqdns=self.cloudfront_cert_validation_records.apply(
                lambda records: [record.name for record in records]
            ),
            opts=pulumi.ResourceOptions(
                provider=aws_east_1,
                parent=self,
                depends_on=self.cloudfront_cert_validation_records
            )
        )

        cache_policy = aws.cloudfront.get_cache_policy(name="UseOriginCacheControlHeaders-QueryStrings")
        error_page_policy = aws.cloudfront.get_cache_policy(name="Managed-CachingOptimized")
        origin_request_policy = aws.cloudfront.get_origin_request_policy(name="Managed-AllViewer")
        response_header_policy = aws.cloudfront.get_response_headers_policy("5cc3b908-e619-4b99-88e5-2cf7f45965bd")

        # Include all domains in CloudFront aliases
        aliases = [full_name] + additional_domains

        self.cloudfront_distribution = aws.cloudfront.Distribution(
            qualify_component_name("cloudfront", self.kwargs),
            enabled=True,
            origins=[
                aws.cloudfront.DistributionOriginArgs(
                    domain_name=self.load_balancer.dns_name,
                    origin_id=self.load_balancer.dns_name,
                    custom_origin_config=aws.cloudfront.DistributionOriginCustomOriginConfigArgs(
                        http_port=80,
                        https_port=443,
                        origin_protocol_policy="https-only",
                        origin_ssl_protocols=["TLSv1.2"],
                    ),
                ),
                aws.cloudfront.DistributionOriginArgs(
                    domain_name=f"{cdn_bucket}.s3.us-west-2.amazonaws.com",
                    origin_id=f"{cdn_bucket}.s3.us-west-2.amazonaws.com",
                )
            ],
            default_root_object="",
            aliases=aliases,
            viewer_certificate=aws.cloudfront.DistributionViewerCertificateArgs(
                acm_certificate_arn=self.cloudfront_cert.arn,
                ssl_support_method="sni-only",
                minimum_protocol_version="TLSv1.2_2021",
            ),
            opts=pulumi.ResourceOptions(
                depends_on=[self.cloudfront_cert_validation, self.cloudfront_cert]  # Ensure CloudFront waits for certificate creation and validation
            ),
            ordered_cache_behaviors=[
                aws.cloudfront.DistributionOrderedCacheBehaviorArgs(
                    path_pattern="/504.html",
                    target_origin_id=f"{cdn_bucket}.s3.us-west-2.amazonaws.com",
                    viewer_protocol_policy="allow-all",
                    allowed_methods=["GET", "HEAD"],
                    cached_methods=["GET", "HEAD"],
                    cache_policy_id=error_page_policy.id,
                    response_headers_policy_id=response_header_policy.id,
                    compress=True,
                )
            ],
            default_cache_behavior=aws.cloudfront.DistributionDefaultCacheBehaviorArgs(
                target_origin_id=self.load_balancer.dns_name,
                viewer_protocol_policy="redirect-to-https",
                allowed_methods=["GET", "HEAD", "OPTIONS", "PUT", "PATCH", "POST", "DELETE"],
                cached_methods=["GET", "HEAD"],
                cache_policy_id=cache_policy.id,
                origin_request_policy_id=origin_request_policy.id,
                compress=True,
            ),
            custom_error_responses=[
                aws.cloudfront.DistributionCustomErrorResponseArgs(
                    error_code=504,
                    response_code=504,
                    response_page_path="/504.html",
                    error_caching_min_ttl=10
                )
            ],
            restrictions=aws.cloudfront.DistributionRestrictionsArgs(
                geo_restriction=aws.cloudfront.DistributionRestrictionsGeoRestrictionArgs(
                    restriction_type="none"
                )
            ),
            tags=self.tags,
        )

        dns_target = self.cloudfront_distribution.domain_name
        if self.kwargs.get('cname', True):
            # Create CNAME records for all domains
            def create_cname_records(distribution_domain_name):
                records = [
                    Record(
                        qualify_component_name('cname_record', self.kwargs),  # Use original name for primary domain
                        name=name,
                        type='CNAME',
                        zone_id=zone_id,
                        content=distribution_domain_name,
                        ttl=1,
                        opts=pulumi.ResourceOptions(parent=self, depends_on=[self.cloudfront_distribution])
                    )
                ]
                
                # Add records for additional domains
                for domain in additional_domains:
                    domain_prefix = domain.split('.')[0]
                    records.append(Record(
                        qualify_component_name(f'cname_record_{domain_prefix}', self.kwargs),
                        name=domain_prefix,
                        type='CNAME',
                        zone_id=zone_id,
                        content=distribution_domain_name,
                        ttl=1,
                        opts=pulumi.ResourceOptions(parent=self, depends_on=[self.cloudfront_distribution])
                    ))
                
                # Export CNAME validation information
                for record in records:
                    pulumi.export(
                        f"cname_validation_{record.name}",
                        pulumi.Output.all(record.name, record.content).apply(
                            lambda args: f"CNAME Record: {args[0]}.strongmind.com -> {args[1]}"
                        )
                    )
                
                return records

            self.cname_records = dns_target.apply(create_cname_records)

            # Export CloudFront distribution information
            if self.kwargs.get('use_cloudfront', True):
                pulumi.export("cloudfront_domain", self.cloudfront_distribution.domain_name)
                if additional_domains:
                    pulumi.export("cloudfront_aliases", pulumi.Output.format("Additional aliases: {}", ", ".join(additional_domains)))

            pulumi.export("url", Output.concat("https://", full_name))

    def certificate(self, name, stack):
        if stack != "prod":
            name = f"{stack}-{name}"
        name = self.kwargs.get('namespace', name)
        domain = 'strongmind.com'
        full_name = f"{name}.{domain}"
        self.cert = aws.acm.Certificate(
            qualify_component_name("cert", self.kwargs),
            domain_name=full_name,
            validation_method="DNS",
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )
