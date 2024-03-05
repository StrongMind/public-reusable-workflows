import pulumi
import pulumi_aws as aws
from pulumi_cloudflare import get_zone, Record
from pulumi import Output
import re

"""
This file contains the CloudFront component from Pulumi. This component is meant to be called by other projects to deploy a 
Cloudfront distribution. The required parameters are the resource_name, origin_domain, and the default_root_object.
@overload
def Distribution(resource_name: str,
                 opts: Optional[ResourceOptions] = None,
                 aliases: Optional[Sequence[str]] = None,
                 comment: Optional[str] = None,
                 continuous_deployment_policy_id: Optional[str] = None,
                 custom_error_responses: Optional[Sequence[DistributionCustomErrorResponseArgs]] = None,
                 default_cache_behavior: Optional[DistributionDefaultCacheBehaviorArgs] = None,
                 default_root_object: Optional[str] = None,
                 enabled: Optional[bool] = None,
                 http_version: Optional[str] = None,
                 is_ipv6_enabled: Optional[bool] = None,
                 logging_config: Optional[DistributionLoggingConfigArgs] = None,
                 ordered_cache_behaviors: Optional[Sequence[DistributionOrderedCacheBehaviorArgs]] = None,
                 origin_groups: Optional[Sequence[DistributionOriginGroupArgs]] = None,
                 origins: Optional[Sequence[DistributionOriginArgs]] = None,
                 price_class: Optional[str] = None,
                 restrictions: Optional[DistributionRestrictionsArgs] = None,
                 retain_on_delete: Optional[bool] = None,
                 staging: Optional[bool] = None,
                 tags: Optional[Mapping[str, str]] = None,
                 viewer_certificate: Optional[DistributionViewerCertificateArgs] = None,
                 wait_for_deployment: Optional[bool] = None,
                 web_acl_id: Optional[str] = None)
@overload
def Distribution(resource_name: str,
                 args: DistributionArgs,
                 opts: Optional[ResourceOptions] = None)
"""

class DistributionComponent(pulumi.ComponentResource):
    def __init__(self,name, **kwargs):

        super().__init__("custom:module:DistributionComponent", name, {})
        self.kwargs = kwargs
        self._transformations = []
        self.fqdn = kwargs.get('fqdn', None)

        stack = kwargs.get('stack')
        origin_domain = kwargs.get('origin_domain')
        origin_id = f"{name}-origin"
        self.tags = {
            "name": name,
            "stack": stack
        }

        self.dns(stack)
        self.distribution = aws.cloudfront.Distribution(f"{name}-distribution",
          opts=pulumi.ResourceOptions(parent=self),
          enabled=True,
          origins=[aws.cloudfront.DistributionOriginArgs(
            domain_name=origin_domain,
            origin_id=origin_id,
          )],
          default_root_object=kwargs.get('default_root_object'),
          aliases=[kwargs.get('fqdn', None)],
          viewer_certificate=aws.cloudfront.DistributionViewerCertificateArgs(
            acm_certificate_arn=self.cert_validation_cert.certificate_arn,
            ssl_support_method="sni-only",
            minimum_protocol_version="TLSv1.2_2021",
            cloudfront_default_certificate=True),
          comment="",
          price_class="PriceClass_All",
          default_cache_behavior=aws.cloudfront.DistributionDefaultCacheBehaviorArgs(
            allowed_methods=["GET", "HEAD", "OPTIONS", "PUT", "PATCH", "POST", "DELETE"],
            cached_methods=["GET", "HEAD"],
            target_origin_id=origin_id,
            viewer_protocol_policy="redirect-to-https",
            compress=True,
            default_ttl=0,
            max_ttl=0,
            min_ttl=0,
            forwarded_values=aws.cloudfront.DistributionDefaultCacheBehaviorForwardedValuesArgs(
              query_string=False,
            cookies=aws.cloudfront.DistributionDefaultCacheBehaviorForwardedValuesCookiesArgs(
              forward="none",
            )),
          ),
          restrictions=aws.cloudfront.DistributionRestrictionsArgs(
            geo_restriction=aws.cloudfront.DistributionRestrictionsGeoRestrictionArgs(
              restriction_type="none"
              )
          ),
)
        self.cname(distribution_domain_name=self.distribution.domain_name)

    def dns(self, stack):
     
        aws_east_1 = aws.Provider("aws-east-1", region="us-east-1")
        full_name = self.kwargs.get('fqdn')
        zone_id = self.kwargs.get('zone_id', 'b4b7fec0d0aacbd55c5a259d1e64fff5')
        pulumi.export("url", Output.concat("https://", full_name))

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
          validation_record_fqdns=[self.cert_validation_record.hostname],
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
