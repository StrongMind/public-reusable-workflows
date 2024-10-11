import pulumi
import pulumi_aws as aws
import json


class DashboardComponent(pulumi.ComponentResource):
    def __init__(self, name, **kwargs):
        super().__init__('strongmind:global_build:commons:dashboard', name)
        self.namespace = kwargs.get("namespace", f"{pulumi.get_project()}-{pulumi.get_stack()}")
        self.web_container = kwargs['web_container']
        self.ecs_cluster = kwargs['ecs_cluster']
        self.rds_serverless_cluster_instance = kwargs['rds_serverless_cluster_instance']
        self.autoscale = kwargs.get('autoscale', False)
        self.kwargs = kwargs
        self.log_metric_filter_definitions = []
        self.load_balancer_arn_name = ""
        self.target_group_arn = ""
        self.setup_dashboard(**kwargs)

    def setup_dashboard(self, **kwargs):
        self.log_metric_filter_definitions = self.kwargs.get('log_metric_filters', [])
        load_balancer_arn = kwargs.get('load_balancer_arn', self.web_container.load_balancer.arn)
        self.load_balancer_arn_name = load_balancer_arn.apply(lambda arn: arn.split("loadbalancer/")[1])
        self.target_group_arn = self.web_container.target_group.arn.apply(lambda arn: arn.split(":")[-1])
        widgets = []

        # Add log metrics widgets
        for log_metric_filter in self.log_metric_filter_definitions:
            widgets.append(self.ecs_cluster.name.apply(lambda name: {
                "type": "metric",
                "x": 0,
                "y": 0,  # Stacking widgets vertically
                "width": 12,
                "height": 6,
                "properties": {
                    "metrics": [
                        [
                            log_metric_filter["metric_transformation"]["namespace"],
                            log_metric_filter["metric_transformation"]["name"],
                            "LogGroupName", f"/aws/ecs/{self.namespace}"
                        ]
                    ],
                    "period": 300,
                    "stat": "Sum",
                    "region": "us-west-2",  # Specify your region
                    "title": log_metric_filter["metric_transformation"]["name"]
                }
            }))

        # ECS CPU Utilization widget
        widgets.append(self.ecs_cluster.name.apply(lambda name: {
            "type": "metric",
            "x": 0,
            "y": 6,
            "width": 12,
            "height": 6,
            "properties": {
                "metrics": [
                    ["AWS/ECS", "CPUUtilization", "ClusterName",
                     self.ecs_cluster.name.apply(lambda cluster_name: cluster_name), "ServiceName",
                     self.web_container.fargate_service.name.apply(lambda service_name: service_name)]
                ],
                "period": 300,
                "stat": "Average",
                "region": "us-west-2",
                "title": "ECS CPU Utilization"
            }
        }))

        # ECS Auto-Scaling Actions widget
        if self.autoscale:
            widgets.append(self.ecs_cluster.name.apply(lambda name: {
                "type": "metric",
                "x": 12,
                "y": 0,
                "width": 12,
                "height": 6,
                "properties": {
                    "metrics": [
                        ["AWS/ApplicationAutoScaling", "NumberOfTasks", "ClusterName",
                         self.ecs_cluster.name.apply(lambda cluster_name: cluster_name), "ServiceName",
                         self.web_container.fargate_service.name.apply(lambda service_name: service_name),
                         {"stat": "SampleCount"}]
                    ],
                    "period": 300,
                    "view": "timeSeries",
                    "stacked": False,
                    "region": "us-west-2",
                    "title": "ECS Auto-Scaling Actions"
                }
            }))
        # ECS Memory Utilization widget
        widgets.append(self.ecs_cluster.name.apply(lambda name: {
            "type": "metric",
            "x": 12,
            "y": 6,
            "width": 12,
            "height": 6,
            "properties": {
                "metrics": [
                    ["AWS/ECS", "MemoryUtilization", "ClusterName",
                     self.ecs_cluster.name.apply(lambda cluster_name: cluster_name), "ServiceName",
                     self.web_container.fargate_service.name.apply(lambda service_name: service_name)]
                ],
                "period": 300,
                "stat": "Average",
                "region": "us-west-2",
                "title": "ECS Memory Utilization"
            }
        }))
        # Healthy Nodes Target Group widget
        widgets.append(self.load_balancer_arn_name.apply(lambda name: {
            "type": "metric",
            "x": 0,
            "y": 12,
            "width": 12,
            "height": 6,
            "properties": {
                "metrics": [
                    ["AWS/ApplicationELB", "HealthyHostCount", "LoadBalancer",
                     self.load_balancer_arn_name.apply(lambda load_balancer_arn_name: load_balancer_arn_name),
                     "TargetGroup", self.target_group_arn.apply(lambda target_group_arn: target_group_arn)]
                ],
                "period": 300,
                "stat": "Minimum",
                "region": "us-west-2",
                "title": "Healthy Hosts (Minimum)"
            }
        }))
        # Request Count widget
        widgets.append(self.load_balancer_arn_name.apply(lambda name: {
            "type": "metric",
            "x": 12,
            "y": 24,
            "width": 12,
            "height": 6,
            "properties": {
                "metrics": [
                    ["AWS/ApplicationELB", "RequestCount", "LoadBalancer",
                     self.load_balancer_arn_name.apply(lambda load_balancer_arn_name: load_balancer_arn_name),
                     {"stat": "Sum"}]
                ],
                "period": 300,
                "stat": "Sum",
                "region": "us-west-2",
                "title": "LB Request Count"
            }
        }))
        # Target Response Time widget
        widgets.append(self.load_balancer_arn_name.apply(lambda name: {
            "type": "metric",
            "x": 12,
            "y": 30,
            "width": 12,
            "height": 6,
            "properties": {
                "metrics": [
                    ["AWS/ApplicationELB", "TargetResponseTime", "LoadBalancer",
                     self.load_balancer_arn_name.apply(lambda load_balancer_arn_name: load_balancer_arn_name),
                     {"stat": "Average"}]
                ],
                "period": 300,
                "stat": "Average",
                "region": "us-west-2",
                "title": "LB Target Response Time"
            }
        }))
        # HTTP 5XX Count widget
        widgets.append(self.load_balancer_arn_name.apply(lambda name: {
            "type": "metric",
            "x": 12,
            "y": 36,
            "width": 12,
            "height": 6,
            "properties": {
                "metrics": [
                    ["AWS/ApplicationELB", "HTTPCode_Target_5XX_Count", "LoadBalancer",
                     self.load_balancer_arn_name.apply(lambda load_balancer_arn_name: load_balancer_arn_name),
                     {"stat": "Sum"}]
                ],
                "period": 300,
                "stat": "Sum",
                "region": "us-west-2",
                "title": "LB HTTP 5XX Count"
            }
        }))
        # HTTP 4XX Count widget
        widgets.append(self.load_balancer_arn_name.apply(lambda name: {
            "type": "metric",
            "x": 12,
            "y": 42,
            "width": 12,
            "height": 6,
            "properties": {
                "metrics": [
                    ["AWS/ApplicationELB", "HTTPCode_Target_4XX_Count", "LoadBalancer",
                     self.load_balancer_arn_name.apply(lambda load_balancer_arn_name: load_balancer_arn_name),
                     {"stat": "Sum"}]
                ],
                "period": 300,
                "stat": "Sum",
                "region": "us-west-2",
                "title": "LB HTTP 4XX Count"
            }
        }))
        # RDS CPU Utilization widget
        widgets.append(self.rds_serverless_cluster_instance.identifier.apply(lambda name: {
            "type": "metric",
            "x": 0,
            "y": 18,
            "width": 12,
            "height": 6,
            "properties": {
                "metrics": [
                    ["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier",
                     self.rds_serverless_cluster_instance.identifier.apply(lambda identifier: identifier)]
                ],
                "period": 300,
                "stat": "Average",
                "region": "us-west-2",
                "title": "RDS CPU Utilization"
            }
        }))
        # RDS Database Connections widget
        widgets.append(self.rds_serverless_cluster_instance.identifier.apply(lambda name: {
            "type": "metric",
            "x": 0,
            "y": 24,
            "width": 12,
            "height": 6,
            "properties": {
                "metrics": [
                    ["AWS/RDS", "DatabaseConnections", "DBInstanceIdentifier",
                     self.rds_serverless_cluster_instance.identifier.apply(lambda identifier: identifier)]
                ],
                "period": 300,
                "stat": "Average",
                "region": "us-west-2",
                "title": "RDS Database Connections"
            }
        }))
        # RDS ACUUtilization widget
        widgets.append(self.rds_serverless_cluster_instance.identifier.apply(lambda name: {
            "type": "metric",
            "x": 0,
            "y": 30,
            "width": 12,
            "height": 6,
            "properties": {
                "metrics": [
                    ["AWS/RDS", "ACUUtilization", "DBInstanceIdentifier",
                     self.rds_serverless_cluster_instance.identifier.apply(lambda identifier: identifier)]
                ],
                "period": 300,
                "stat": "Average",
                "region": "us-west-2",
                "title": "RDS ACU Utilization"
            }
        }))

        dashboard_body = pulumi.Output.all(*widgets).apply(lambda ws: json.dumps({"widgets": ws}))

        dashboard = aws.cloudwatch.Dashboard(f"{self.namespace}-dashboard",
                                             dashboard_body=dashboard_body,
                                             dashboard_name=f"{self.namespace}")
