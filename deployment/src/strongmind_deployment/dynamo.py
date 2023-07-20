import pulumi
import pulumi_aws as aws
from pulumi import ResourceOptions


class DynamoComponent(pulumi.ComponentResource):
    def __init__(self, name, opts=None, **kwargs):
        super().__init__('strongmind:global_build:commons:dynamo', name, None, opts)
        project = pulumi.get_project()
        stack = pulumi.get_stack()
        table_opts = ResourceOptions(ignore_changes=["read_capacity", "write_capacity"])  # pragma: no cover
        self.table = aws.dynamodb.Table(
            name,
            name=f"{project}-{stack}-{name}",
            attributes=kwargs.get("attributes"),
            opts=table_opts
        )
