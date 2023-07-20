import pulumi
import pulumi_aws as aws


class DynamoComponent(pulumi.ComponentResource):
    def __init__(self, name, opts=None, **kwargs):
        super().__init__('strongmind:global_build:commons:dynamo', name, None, opts)
        project = pulumi.get_project()
        stack = pulumi.get_stack()
        self.table = aws.dynamodb.Table(
            name,
            name=f"{project}-{stack}-{name}",
        )
