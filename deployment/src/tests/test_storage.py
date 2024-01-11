import pulumi.runtime
import pulumi_aws.s3
import pytest
import json

from tests.mocks import get_pulumi_mocks
from tests.shared import assert_output_equals, assert_outputs_equal


def describe_a_pulumi_storage_component():
    @pytest.fixture
    def app_name(faker):
        return faker.word()

    @pytest.fixture
    def environment(faker):
        return faker.word()

    @pytest.fixture
    def stack(faker, app_name, environment):
        return f"{environment}"

    @pytest.fixture
    def pulumi_mocks(faker):
        return get_pulumi_mocks(faker)

    @pytest.fixture
    def name(faker):
        return faker.word()

    @pytest.fixture
    def component_arguments():
        return {}

    @pytest.fixture
    def sut(pulumi_set_mocks,
            component_arguments,
            name):
        import strongmind_deployment.storage

        sut = strongmind_deployment.storage.StorageComponent(name,
                                                         **component_arguments
                                                         )
        return sut

    def it_exists(sut):
        assert sut

    def describe_a_storage_bucket():
        def it_has_a_bucket(sut):
            assert sut.bucket

        @pulumi.runtime.test
        def it_is_an_aws_s3_bucket_v2(sut):
            assert isinstance(sut.bucket, pulumi_aws.s3.BucketV2)

        @pulumi.runtime.test
        def it_has_a_bucket_name(sut, app_name, stack):
            return assert_output_equals(sut.bucket.bucket, f"strongmind-{app_name}-{stack}")

        @pulumi.runtime.test
        def it_has_tags(sut, app_name):
            return assert_output_equals(sut.bucket.tags, {
                "product": app_name,
                "repository": app_name,
                "service": app_name,
                "environment": sut.env_name,
            })

    def describe_ownership_controls():
        def it_has_ownership_controls(sut):
            assert isinstance(sut.bucket_ownership_controls, pulumi_aws.s3.BucketOwnershipControls)

        @pulumi.runtime.test
        def it_has_bucket_id(sut):
            return assert_outputs_equal(sut.bucket_ownership_controls.bucket, sut.bucket.id)

        @pulumi.runtime.test
        def it_prefers_bucket_owner(sut):
            return assert_output_equals(sut.bucket_ownership_controls.rule.object_ownership, "BucketOwnerPreferred")

    def describe_public_access_block():
        def it_has_a_public_access_block(sut):
            assert isinstance(sut.bucket_public_access_block, pulumi_aws.s3.BucketPublicAccessBlock)

        @pulumi.runtime.test
        def it_has_bucket_id(sut):
            return assert_outputs_equal(sut.bucket_public_access_block.bucket, sut.bucket.id)

        @pulumi.runtime.test
        def it_blocks_public_acls(sut):
            return assert_output_equals(sut.bucket_public_access_block.block_public_acls, True)
        
        def describe_when_storage_is_set_to_public():
            @pytest.fixture
            def component_arguments():
                return {
                    "storage_private": False
                }

            @pulumi.runtime.test
            def it_blocks_public_access(sut):
                return assert_output_equals(sut.bucket_public_access_block.block_public_acls, False)

    def describe_acls():
        def it_has_acls(sut):
            assert isinstance(sut.bucket_acl, pulumi_aws.s3.BucketAclV2)

        @pulumi.runtime.test
        def it_has_bucket_id(sut):
            return assert_outputs_equal(sut.bucket_acl.bucket, sut.bucket.id)

        @pulumi.runtime.test
        def it_has_private_access(sut):
            return assert_output_equals(sut.bucket_acl.acl, "private")
        
    def describe_s3_user():
        def it_has_a_user(sut):
            assert sut.s3_user

        @pulumi.runtime.test
        def it_is_an_aws_iam_user(sut):
            assert isinstance(sut.s3_user, pulumi_aws.iam.User)
        
    def describe_s3_policy():
        def it_has_a_policy(sut):
            assert isinstance(sut.s3_policy, pulumi_aws.iam.Policy)
        
        @pulumi.runtime.test
        def it_has_a_policy_document(sut):
            return assert_output_equals(sut.s3_policy.policy, json.dumps({
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Action": [
                        "s3:GetObject",
                        "s3:PutObject",
                        "s3:DeleteObject"
                    ],
                    "Resource": [f"arn:aws:s3:::{sut.bucket.bucket}/*"]
                }]
            }))


    def describe_s3_access_key():
        def it_has_an_access_key(sut):
            assert sut.s3_user_secret_access_key
        
        def it_is_an_aws_iam_access_key(sut):
            assert isinstance(sut.s3_user_secret_access_key, pulumi_aws.iam.AccessKey)

        @pulumi.runtime.test
        def it_has_a_user(sut):
            return assert_outputs_equal(sut.s3_user_secret_access_key.user, sut.s3_user.name)
        
