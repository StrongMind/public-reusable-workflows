import pulumi
import pulumi_aws as aws


class DynamoComponent(pulumi.ComponentResource):
    def __init__(self, name, opts=None, **kwargs):
        self.table = aws.dynamodb.Table(name)
