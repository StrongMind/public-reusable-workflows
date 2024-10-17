import os
import subprocess

import pulumi
import pulumi_aws as aws
import json

from strongmind_deployment.util import qualify_component_name


class StorageComponent(pulumi.ComponentResource):
    def __init__(self, name, *args, **kwargs):
        self.env_name = os.environ.get('ENVIRONMENT_NAME', 'stage')
        self.kwargs = kwargs

        project = pulumi.get_project()
        stack = pulumi.get_stack()
        bucket_name = f"strongmind-{project}-{stack}"
        path = subprocess.check_output(['git', 'rev-parse', '--show-toplevel']).decode('utf-8').strip()
        file_path = f"{path}/CODEOWNERS"
        with open(file_path, 'r') as file:
            owning_team = [line.strip().split('@')[-1] for line in file if '@' in line][-1].split('/')[1]

        tags = {
            "product": project,
            "repository": project,
            "service": project,
            "environment": self.env_name,
            "owner": owning_team,
        }
        self.bucket = aws.s3.BucketV2(qualify_component_name("bucket", self.kwargs),
                                      bucket=bucket_name,
                                      tags=tags
                                      )

        self.bucket_ownership_controls = aws.s3.BucketOwnershipControls(qualify_component_name("bucket_ownership_controls", self.kwargs),
                                                                        bucket=self.bucket.id,
                                                                        rule=aws.s3.BucketOwnershipControlsRuleArgs(
                                                                            object_ownership="BucketOwnerPreferred",
                                                                        ))
        self.bucket_public_access_block = aws.s3.BucketPublicAccessBlock(qualify_component_name("bucket_public_access_block", self.kwargs),
                                                                         bucket=self.bucket.id,
                                                                         block_public_acls=kwargs.get('storage_private', True),
                                                                         block_public_policy=kwargs.get('storage_private', True),
                                                                         ignore_public_acls=kwargs.get('storage_private', True),
                                                                         restrict_public_buckets=kwargs.get('storage_private', True)
                                                                         )

        acl_opts = pulumi.ResourceOptions(
            depends_on=[self.bucket_ownership_controls, self.bucket_public_access_block])  # pragma: no cover
        if kwargs.get('storage_private') == False:
            acl = "public-read"
        else:
            acl = "private"
        self.bucket_acl = aws.s3.BucketAclV2(qualify_component_name("bucket_acl", self.kwargs),
                                             bucket=self.bucket.id,
                                             acl=acl,
                                             opts=acl_opts
                                             )

        self.s3_env_vars = {
            "S3_BUCKET_NAME": self.bucket.bucket,
        }
