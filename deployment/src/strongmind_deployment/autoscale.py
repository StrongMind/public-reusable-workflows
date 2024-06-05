import pulumi
import pulumi_aws as aws

class AutoscaleComponent(pulumi.ComponentResource):
    def __init__(self, name, opts=None, **kwargs):
        super().__init__('strongmind:global_build:commons:autoscale', name, None, opts)
        self.project_stack = pulumi.get_project() + "-" + pulumi.get_stack()
        self.max_capacity = kwargs.get("max_capacity", 10)
        self.min_capacity = kwargs.get("min_capacity", 1)
        self.autoscaling()
    def autoscaling(self):

        self.autoscaling_target = aws.appautoscaling.Target(
            "autoscaling_target",
            max_capacity=self.max_capacity,
            min_capacity=self.min_capacity,
            resource_id=f"service/{self.project_stack}/{self.project_stack}",
            scalable_dimension="ecs:service:DesiredCount",
            service_namespace="ecs",
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
            evaluation_periods=1,
            metric_name="CPUUtilization",
            unit="Percent",
            dimensions={
                "ClusterName": self.project_stack,
                "ServiceName": self.project_stack
            },
            namespace="AWS/ECS",
            period=60,
            statistic="Average",
            threshold=65,
            alarm_actions=[self.autoscaling_out_policy.arn]
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
            evaluation_periods=5,
            metric_name="CPUUtilization",
            unit="Percent",
            dimensions={
                "ClusterName": self.project_stack,
                "ServiceName": self.project_stack
            },
            namespace="AWS/ECS",
            period=60,
            statistic="Average",
            threshold=50,
            alarm_actions=[self.autoscaling_in_policy.arn]
        )

class WorkerAutoscaleComponent(pulumi.ComponentResource):
    def __init__(self, name, opts=None, **kwargs):
        """
        :key worker_max_number_of_instances: The maximum number of instances available in the scaling policy for the worker.
        :key worker_min_number_of_instances: The minimum number of instances available in the scaling policy for the worker.
        :key worker_autoscale_threshold: The threshold for the worker autoscaling policy. Default is 3.
        """
        super().__init__('strongmind:global_build:commons:worker-autoscale', name, None, opts)
        self.project_stack = pulumi.get_project() + "-" + pulumi.get_stack()
        self.worker_max_capacity = kwargs.get('worker_max_number_of_instances', 1)
        self.worker_min_capacity = kwargs.get('worker_min_number_of_instances', 1)
        self.threshold = kwargs.get('worker_autoscale_threshold', 3)
        self.worker_autoscaling()

# scale out based on EnqueuedJobs metric
    def worker_autoscaling(self):
        self.worker_autoscaling_target = aws.appautoscaling.Target(
            "worker_autoscaling_target",
            max_capacity=self.worker_max_capacity,
            min_capacity=self.worker_min_capacity,
            resource_id=f"service/{self.project_stack}/{self.project_stack}-worker",
            scalable_dimension="ecs:service:DesiredCount",
            service_namespace="ecs",
        )
        self.worker_autoscaling_out_policy = aws.appautoscaling.Policy(
            "worker_autoscaling_out_policy",
            name=f"{self.project_stack}-worker-autoscaling-out-policy",
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
        self.worker_autoscaling_out_alarm = aws.cloudwatch.MetricAlarm(
            "worker_autoscaling_out_alarm",
            name=f"{self.project_stack}-worker-auto-scaling-out-alarm",
            comparison_operator="GreaterThanThreshold",
            evaluation_periods=1,
            metric_name="EnqueuedJobs",
            unit="Count",
# DIMENSIONS ARE COMMENTED HERE until we can update the sidekiqcloudwatchmetrcis gem to accept dimeensions
#             dimensions={
#                 "ClusterName": self.project_stack,
#                 "ServiceName": self.project_stack
#             },
            namespace=self.project_stack,
            period=60,
            statistic="Maximum",
            threshold=self.threshold,
            alarm_actions=[self.worker_autoscaling_out_policy.arn]
        )
        self.worker_autoscaling_in_policy = aws.appautoscaling.Policy(
            "worker_autoscaling_in_policy",
            name=f"{self.project_stack}-worker-autoscaling-in-policy",
            policy_type="StepScaling",
            resource_id=self.worker_autoscaling_target.resource_id,
            scalable_dimension=self.worker_autoscaling_target.scalable_dimension,
            service_namespace=self.worker_autoscaling_target.service_namespace,
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
        self.worker_autoscaling_in_alarm = aws.cloudwatch.MetricAlarm(
            "worker_autoscaling_in_alarm",
            name=f"{self.project_stack}-worker-auto-scaling-in-alarm",
            comparison_operator="LessThanOrEqualToThreshold",
            evaluation_periods=5,
            metric_name="EnqueuedJobs",
            unit="Count",
# DIMENSIONS ARE COMMENTED HERE until we can update the sidekiqcloudwatchmetrcis gem to accept dimeensions
#             dimensions={
#                 "ClusterName": self.project_stack,
#                 "ServiceName": self.project_stack
#             },
            namespace=self.project_stack,
            period=60,
            statistic="Maximum",
            threshold=2,
            alarm_actions=[self.worker_autoscaling_in_policy.arn]
        )
        self.register_outputs({})