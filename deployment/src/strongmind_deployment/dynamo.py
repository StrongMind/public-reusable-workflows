import pulumi
import pulumi_aws as aws
from pulumi import ResourceOptions


class DynamoComponent(pulumi.ComponentResource):
    def __init__(self, name, opts=None, **kwargs):
        """
        Resource that creates a Dynamo Table.

        :param name: The _unique_ name of the resource.
        :param opts: Not used in this resource, but provided for consistency with Pulumi components.
        :key attributes: A dictionary of attributes to create the table with the key as the attribute name and the value as the type. ``{"id": "N", "data": "S"}`` for example. See https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.NamingRulesDataTypes.html#HowItWorks.DataTypeDescriptors for types.
        """
        super().__init__('strongmind:global_build:commons:dynamo', name, None, opts)
        project = pulumi.get_project()
        stack = pulumi.get_stack()
        table_opts = ResourceOptions(ignore_changes=["read_capacity", "write_capacity"])  # pragma: no cover
        attributes = []
        for attribute_name, attribute_type in kwargs.get("attributes", {}).items():
            attributes.append(aws.dynamodb.TableAttributeArgs(name=attribute_name, type=attribute_type))
        self.table = aws.dynamodb.Table(
            name,
            name=f"{project}-{stack}-{name}",
            attributes=attributes,
            opts=table_opts
        )
