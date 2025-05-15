import pulumi
import pulumi_aws as aws
from pulumi_cloudflare import get_zone, Record
from pulumi import Output
from strongmind_deployment.storage import StorageComponent
import re
import os

"""
This file contains the CloudFront component from Pulumi. This component is meant to be called by other projects to deploy a 
Cloudfront distribution. 
The required parameters for the project name and fqdn. DistributionComponent(name="my-cdn-project", fqdn="my-cdn.example.com")

"""

class DistributionComponent(pulumi.ComponentResource):
    def __init__(self,name, **kwargs):

        super().__init__("custom:module:DistributionComponent", name, {})
        self.kwargs = kwargs
        self._transformations = []
        self.fqdn = kwargs.get('fqdn', None)

        fqdn_prefix = self.fqdn.split('.')[:2]
        fqdn_prefix = '.'.join(fqdn_prefix)
        fqdn_prefix = fqdn_prefix.replace('.', '-')
        bucket = StorageComponent(fqdn_prefix, storage_private=False)
        public_bucket_policy_document = aws.iam.get_policy_document_output(statements=[
          aws.iam.GetPolicyDocumentStatementArgs(
            principals=[aws.iam.GetPolicyDocumentStatementPrincipalArgs(
              type="AWS",
              identifiers=["*"],
            )],
          actions=[
            "s3:GetObject",
            "s3:ListBucket",
          ],
          resources=[
            bucket.bucket.arn,
            bucket.bucket.arn.apply(lambda arn: f"{arn}/*"),
          ],
         ),
        ])
        public_bucket_policy = aws.s3.BucketPolicy("public_bucket_policy",
        bucket=bucket.bucket.id,
        policy=public_bucket_policy_document.json)        

        bucket_cors_configuration_v2 = aws.s3.BucketCorsConfigurationV2("s3_cors",
          bucket=bucket.bucket.id,
          cors_rules=[
          aws.s3.BucketCorsConfigurationV2CorsRuleArgs(
            allowed_headers=["*"],
            allowed_methods=[
                "HEAD",
                "GET",
            ],
            allowed_origins=["*"],
            expose_headers=["ETag"],
            max_age_seconds=3000,
          ),
        ])

        stack = kwargs.get('stack')
        origin_domain = bucket.bucket.bucket_regional_domain_name
        origin_id = f"{fqdn_prefix}-origin"
        cors_with_preflight_policy_id = "5cc3b908-e619-4b99-88e5-2cf7f45965bd"

        self.env_name = os.environ.get('ENVIRONMENT_NAME', 'stage')
        project = pulumi.get_project()
        stack = pulumi.get_stack()
        with open('../CODEOWNERS', 'r') as file:
            owning_team = [line.strip().split('@')[-1] for line in file if '@' in line][-1].split('/')[1]

        self.tags = {
            "product": project,
            "repository": project,
            "service": project,
            "environment": self.env_name,
            "owner": owning_team,
        }

        self.dns()
        cache_policy = aws.cloudfront.get_cache_policy(name="Managed-CachingOptimized")
        self.distribution = aws.cloudfront.Distribution(f"{fqdn_prefix}-distribution",
          opts=pulumi.ResourceOptions(parent=self),
          enabled=True,
          origins=[aws.cloudfront.DistributionOriginArgs(
            domain_name=origin_domain,
            origin_id=origin_id,
          )],
          default_root_object="index.html",
          aliases=[kwargs.get('fqdn', None)],
          viewer_certificate=aws.cloudfront.DistributionViewerCertificateArgs(
            acm_certificate_arn=self.cert_validation_cert.certificate_arn,
            ssl_support_method="sni-only",
            minimum_protocol_version="TLSv1.2_2021",
            cloudfront_default_certificate=True),
          comment="",
          price_class="PriceClass_All",
          default_cache_behavior=aws.cloudfront.DistributionDefaultCacheBehaviorArgs(
            cache_policy_id=cache_policy.id,
            allowed_methods=["GET", "HEAD", "OPTIONS", "PUT", "PATCH", "POST", "DELETE"],
            cached_methods=["GET", "HEAD"],
            target_origin_id=origin_id,
            viewer_protocol_policy="redirect-to-https",
            compress=True,
            default_ttl=0,
            max_ttl=0,
            min_ttl=0,
            response_headers_policy_id=cors_with_preflight_policy_id,
          ),
          restrictions=aws.cloudfront.DistributionRestrictionsArgs(
            geo_restriction=aws.cloudfront.DistributionRestrictionsGeoRestrictionArgs(
              restriction_type="none"
              )
          ),
          tags=self.tags,
)
        self.cname(distribution_domain_name=self.distribution.domain_name)

    def dns(self):
     
        aws_east_1 = aws.Provider("aws-east-1", region="us-east-1")
        full_name = self.kwargs.get('fqdn')
        zone_id = self.kwargs.get('zone_id', 'b4b7fec0d0aacbd55c5a259d1e64fff5')

        self.cert = aws.acm.Certificate(
          "cert",
          domain_name=full_name,
          validation_method="DNS",
          tags=self.kwargs.get('tags'),
          opts=pulumi.ResourceOptions(parent=self, provider=aws_east_1),
        )
        domain_validation_options = self.kwargs.get('domain_validation_options',
          self.cert.domain_validation_options) 

        resource_record_value = domain_validation_options[0].resource_record_value

        def remove_trailing_period(value):
            return re.sub("\\.$", "", value)

        if type(resource_record_value) != str:
            resource_record_value = resource_record_value.apply(remove_trailing_period)

        self.cert_validation_record = Record(
          'cert_validation_record',
          name=domain_validation_options[0].resource_record_name,
          type=domain_validation_options[0].resource_record_type,
          zone_id=zone_id,
          value=resource_record_value,
          ttl=1,
          opts=pulumi.ResourceOptions(parent=self, depends_on=[self.cert]),
        )

        self.cert_validation_cert = aws.acm.CertificateValidation(
          "cert_validation",
          certificate_arn=self.cert.arn,
          validation_record_fqdns=[self.cert_validation_record.name],
          opts=pulumi.ResourceOptions(parent=self, depends_on=[self.cert_validation_record], provider=aws_east_1),
        )
        return self.cert_validation_cert.certificate_arn


    def cname(self, distribution_domain_name):
      full_name = self.kwargs.get('fqdn')
      zone_id = self.kwargs.get('zone_id', 'b4b7fec0d0aacbd55c5a259d1e64fff5')
      self.cname_record = Record(
        'cname_record',
        name=full_name,
        type='CNAME',
        zone_id=zone_id,
        value=distribution_domain_name,
        ttl=1,
        )
