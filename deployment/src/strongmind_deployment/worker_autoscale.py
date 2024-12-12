import pulumi
import pulumi_aws as aws

from strongmind_deployment.util import qualify_component_name


class WorkerAutoscaleComponent(pulumi.ComponentResource):
    def __init__(self, name, opts=None, **kwargs):
        """
        :key worker_max_number_of_instances: The maximum number of instances available in the scaling policy for the worker.
        :key worker_min_number_of_instances: The minimum number of instances available in the scaling policy for the worker.
        :key worker_autoscale_threshold: The threshold for the worker autoscaling policy. Default is 3.
        """
        super().__init__('strongmind:global_build:commons:worker-autoscale', name, None, opts)
        self.fargate_service = kwargs.get('fargate_service')
        self.worker_autoscaling_in_alarm = None
        self.worker_autoscaling_in_policy = None
        self.worker_queue_latency_alarm = None
        self.worker_autoscaling_out_alarm = None
        self.worker_autoscaling_out_policy = None
        self.worker_autoscaling_target = None
        self.kwargs = kwargs
        self.namespace = kwargs.get("namespace", f"{pulumi.get_project()}-{pulumi.get_stack()}")
        self.worker_max_capacity = kwargs.get('worker_max_number_of_instances', 65)
        self.worker_min_capacity = kwargs.get('worker_min_number_of_instances', 1)
        self.scaling_threshold = kwargs.get('max_queue_latency_threshold', 60)
        self.alert_threshold = kwargs.get('alert_threshold', 18000)
        self.sns_topic_arn = kwargs.get('sns_topic_arn')
        self.canvas = kwargs.get("namespace", False)
        self.metric_name = "JobStaleness" if self.canvas else "MaxQueueLatency"
        self.dimensions = {'domain': f'{self.namespace}.strongmind.com'} if self.canvas else {"QueueName": "AllQueues"}
        self.alarm_namespace = "Canvas" if self.canvas else self.namespace
        self.worker_autoscaling()


    def worker_autoscaling(self):

        fargate_service_id = self.fargate_service.service.id.apply(lambda x: x.split(":")[-1])

        self.worker_autoscaling_target = aws.appautoscaling.Target(
            qualify_component_name("worker_autoscaling_target", self.kwargs),
            max_capacity=self.worker_max_capacity,
            min_capacity=self.worker_min_capacity,
            resource_id=fargate_service_id,
            scalable_dimension="ecs:service:DesiredCount",
            service_namespace="ecs",
            opts=pulumi.ResourceOptions(
                parent=self,
            )
        )
        self.worker_autoscaling_out_policy = aws.appautoscaling.Policy(
            qualify_component_name("worker_autoscaling_out_policy", self.kwargs),
            name=f"{self.namespace}-worker-autoscaling-out-policy",
            policy_type="StepScaling",
            resource_id=self.worker_autoscaling_target.resource_id,
            scalable_dimension=self.worker_autoscaling_target.scalable_dimension,
            service_namespace=self.worker_autoscaling_target.service_namespace,
            step_scaling_policy_configuration=aws.appautoscaling.PolicyStepScalingPolicyConfigurationArgs(
                adjustment_type="ChangeInCapacity",
                cooldown=60,
                metric_aggregation_type="Maximum",
                step_adjustments=[
                    aws.appautoscaling.PolicyStepScalingPolicyConfigurationStepAdjustmentArgs(
                        metric_interval_upper_bound="600",
                        metric_interval_lower_bound="0",
                        scaling_adjustment=1,
                    ),
                    aws.appautoscaling.PolicyStepScalingPolicyConfigurationStepAdjustmentArgs(
                        metric_interval_lower_bound="600",
                        scaling_adjustment=1,
                    )
                ],
            ),
            opts=pulumi.ResourceOptions(
                parent=self,
            )
        )

        self.worker_autoscaling_out_alarm = aws.cloudwatch.MetricAlarm(
            qualify_component_name("worker_autoscaling_out_alarm", self.kwargs),
            name=f"{self.namespace}-worker-auto-scaling-out-alarm",
            comparison_operator="GreaterThanThreshold",
            evaluation_periods=1,
            metric_name=self.metric_name,
            unit="Seconds",
            dimensions=self.dimensions,
            namespace=self.alarm_namespace,
            period=60,
            statistic="Maximum",
            threshold=self.scaling_threshold,
            alarm_actions=[self.worker_autoscaling_out_policy.arn],
            opts=pulumi.ResourceOptions(
                parent=self,
            )
        )

        self.worker_queue_latency_alarm = aws.cloudwatch.MetricAlarm(
            qualify_component_name("worker_queue_latency_alarm", self.kwargs),
            name=f"{self.namespace}-worker-queue-latency-alarm",
            comparison_operator="GreaterThanThreshold",
            evaluation_periods=1,
            metric_name=self.metric_name,
            unit="Seconds",
            dimensions=self.dimensions,
            namespace=self.alarm_namespace,
            period=60,
            statistic="Maximum",
            threshold=self.alert_threshold,
            alarm_actions=[self.sns_topic_arn],
            ok_actions=[self.sns_topic_arn],
            opts=pulumi.ResourceOptions(
                parent=self,
            )
        )

        self.worker_autoscaling_in_policy = aws.appautoscaling.Policy(
            qualify_component_name("worker_autoscaling_in_policy", self.kwargs),
            name=f"{self.namespace}-worker-autoscaling-in-policy",
            policy_type="StepScaling",
            resource_id=self.worker_autoscaling_target.resource_id,
            scalable_dimension=self.worker_autoscaling_target.scalable_dimension,
            service_namespace=self.worker_autoscaling_target.service_namespace,
            step_scaling_policy_configuration=aws.appautoscaling.PolicyStepScalingPolicyConfigurationArgs(
                adjustment_type="ChangeInCapacity",
                cooldown=60,
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
            )
        )

        self.worker_autoscaling_in_alarm = aws.cloudwatch.MetricAlarm(
            qualify_component_name("worker_autoscaling_in_alarm", self.kwargs),
            name=f"{self.namespace}-worker-auto-scaling-in-alarm",
            comparison_operator="LessThanOrEqualToThreshold",
            evaluation_periods=5,
            metric_name=self.metric_name,
            unit="Seconds",
            dimensions=self.dimensions,
            namespace=self.alarm_namespace,
            period=60,
            statistic="Maximum",
            threshold=self.scaling_threshold,
            alarm_actions=[self.worker_autoscaling_in_policy.arn],
            opts=pulumi.ResourceOptions(
                parent=self,
            )
        )

        self.register_outputs({})
