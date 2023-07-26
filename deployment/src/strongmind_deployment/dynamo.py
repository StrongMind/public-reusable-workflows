import pulumi
import pulumi_aws as aws
from pulumi import ResourceOptions


class DynamoComponent(pulumi.ComponentResource):
    def __init__(self, name, opts=None, **kwargs):
        """
        Resource that creates a Dynamo Table.

        :param name: The _unique_ name of the resource.
        :param opts: Not used in this resource, but provided for consistency with Pulumi components.
        :key attributes: A dictionary of the hash key and (optionally) range key attributes with which to create the table. The dictionary's key is the attribute name and the value is the type. ``{"id": "N", "data": "S"}`` for example. See https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.NamingRulesDataTypes.html#HowItWorks.DataTypeDescriptors for types.
        :key hash_key: The name of the hash key attribute, used as partition key. Required. Must be in attributes dictionary.
        :key range_key: The name of the range key attribute, used as sort key. Optional. Must be in attributes dictionary if provided.
        """
        super().__init__('strongmind:global_build:commons:dynamo', name, None, opts)
        project = pulumi.get_project()
        stack = pulumi.get_stack()
        table_opts = ResourceOptions(
            parent=self,
            ignore_changes=["read_capacity", "write_capacity"])  # pragma: no cover
        hash_key = kwargs.get("hash_key")
        if not hash_key:
            raise ValueError("hash_key is required")
        attributes = []
        for attribute_name, attribute_type in kwargs.get("attributes", {}).items():
            attributes.append(aws.dynamodb.TableAttributeArgs(name=attribute_name, type=attribute_type))

        table_name = f"{project}-{stack}-{name}"
        self.table = aws.dynamodb.Table(
            name,
            name=table_name,
            attributes=attributes,
            opts=table_opts,
            read_capacity=1,
            write_capacity=1,
            hash_key=hash_key,
            range_key=kwargs.get("range_key"),
            deletion_protection_enabled=True
        )

        self.read_autoscaling_target = aws.appautoscaling.Target(
            f"{name}-read-autoscaling-target",
            resource_id=f"table/{table_name}",
            max_capacity=40000,
            min_capacity=1,
            scalable_dimension="dynamodb:table:ReadCapacityUnits",
            service_namespace="dynamodb",
            opts=ResourceOptions(
                parent=self,
                depends_on=[self.table]
            )
        )
        self.table_read_policy = aws.appautoscaling.Policy(
            f"{name}-read-autoscaling-policy",
            policy_type="TargetTrackingScaling",
            resource_id=f"table/{table_name}",
            scalable_dimension="dynamodb:table:ReadCapacityUnits",
            service_namespace="dynamodb",
            target_tracking_scaling_policy_configuration=aws.appautoscaling.PolicyTargetTrackingScalingPolicyConfigurationArgs(
                predefined_metric_specification=aws.appautoscaling.PolicyTargetTrackingScalingPolicyConfigurationPredefinedMetricSpecificationArgs(
                    predefined_metric_type="DynamoDBReadCapacityUtilization",
                ),
                target_value=70,
            ),
            opts=ResourceOptions(
                parent=self,
                depends_on=[self.table]
            )
        )
        self.write_autoscaling_target = aws.appautoscaling.Target(
            f"{name}-write-autoscaling-target",
            resource_id=f"table/{table_name}",
            max_capacity=40000,
            min_capacity=1,
            scalable_dimension="dynamodb:table:WriteCapacityUnits",
            service_namespace="dynamodb",
            opts=ResourceOptions(
                parent=self,
                depends_on=[self.table]
            )
        )
        self.table_write_policy = aws.appautoscaling.Policy(
            f"{name}-write-autoscaling-policy",
            policy_type="TargetTrackingScaling",
            resource_id=f"table/{table_name}",
            scalable_dimension="dynamodb:table:WriteCapacityUnits",
            service_namespace="dynamodb",
            target_tracking_scaling_policy_configuration=aws.appautoscaling.PolicyTargetTrackingScalingPolicyConfigurationArgs(
                predefined_metric_specification=aws.appautoscaling.PolicyTargetTrackingScalingPolicyConfigurationPredefinedMetricSpecificationArgs(
                    predefined_metric_type="DynamoDBWriteCapacityUtilization",
                ),
                target_value=70,
            ),
            opts=ResourceOptions(
                parent=self,
                depends_on=[self.table]
            )
        )

        self.register_outputs({})
