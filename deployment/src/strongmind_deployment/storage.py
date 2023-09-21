import os

import pulumi
import pulumi_aws as aws


class StorageComponent(pulumi.ComponentResource):
    def __init__(self, name, *args, **kwargs):
        self.env_name = os.environ.get('ENVIRONMENT_NAME', 'stage')

        project = pulumi.get_project()
        stack = pulumi.get_stack()
        bucket_name = f"strongmind-{project}-{stack}"

        self.bucket = aws.s3.BucketV2("bucket",
                                      bucket=bucket_name,
                                      tags={
                                          "product": project,
                                          "repository": project,
                                          "service": project,
                                          "environment": self.env_name,
                                      }
                                      )

        self.bucket_ownership_controls = aws.s3.BucketOwnershipControls("bucket_ownership_controls",
                                                                        bucket=self.bucket.id,
                                                                        rule=aws.s3.BucketOwnershipControlsRuleArgs(
                                                                            object_ownership="BucketOwnerPreferred",
                                                                        ))
        self.bucket_public_access_block = aws.s3.BucketPublicAccessBlock("bucket_public_access_block",
                                                                         bucket=self.bucket.id,
                                                                         block_public_acls=kwargs.get('storage_private', True),
                                                                         block_public_policy=kwargs.get('storage_private', True),
                                                                         ignore_public_acls=kwargs.get('storage_private', True),
                                                                         restrict_public_buckets=kwargs.get('storage_private', True)
                                                                         )

        acl_opts = pulumi.ResourceOptions(
            depends_on=[self.bucket_ownership_controls, self.bucket_public_access_block])  # pragma: no cover
        self.bucket_acl = aws.s3.BucketAclV2("bucket_acl",
                                             bucket=self.bucket.id,
                                             acl="public-read",
                                             opts=acl_opts
                                             )
