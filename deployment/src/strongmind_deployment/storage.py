import os

import pulumi
import pulumi_aws as aws


class StorageComponent(pulumi.ComponentResource):
    def __init__(self, name, *args, **kwargs):
        self.env_name = os.environ.get('ENVIRONMENT_NAME', 'stage')

        project = pulumi.get_project()
        stack = pulumi.get_stack()
        bucket_name = f"{project}-{stack}-courseware"

        self.bucket = aws.s3.Bucket("bucket",
                                    acl="private",
                                    bucket=bucket_name,
                                    tags={
                                        "product": project,
                                        "repository": project,
                                        "service": project,
                                        "environment": self.env_name,
                                    }
                                    )
