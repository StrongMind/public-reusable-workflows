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
        #self.__dict__.update(kwargs)
        #opts: Optional[pulumi.ResourceOptions] = None):
        #print(f"args passed to DistributionComponent: {args} and kwargs passed to DistributionComponent: {kwargs}\n")

        stack = kwargs.get('stack')
        origin_domain = kwargs.get('origin_domain')
        origin_id = f"{name}-origin"
        aws_cloudfront_origin_access_identity = {
            "identity": {
        "cloudfront_access_identity_path": f"{origin_id}-origin-access-identity"
        }
    }
        aws_cloudfront_origin_access_identity = aws.cloudfront.OriginAccessIdentity(f"{origin_id}-myOriginAccessIdentity",
        comment="")
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
                                                   s3_origin_config=aws.cloudfront.DistributionOriginS3OriginConfigArgs(
                                                       origin_access_identity=aws_cloudfront_origin_access_identity.cloudfront_access_identity_path
                                                    ) 
                                                   )],
                                                   default_root_object=kwargs.get('default_root_object'),
                                                   #logging_config=aws.cloudfront.DistributionLoggingConfigArgs(
                                                   #    bucket=bucket.bucket_regional_domain_name,
                                                   #    include_cookies=False,
                                                   #    prefix=f"cloudfront-{name}-logs"
                                                   #),
                                                   aliases=None,
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
                                                    viewer_certificate=aws.cloudfront.DistributionViewerCertificateArgs(
                                                        cloudfront_default_certificate=True
                                                    ),
)
    # s3_origin_access_identity func is meant to check if the origin_domain contains s3. 
    # If it does, we will create an origin_access_identity resource for the distribution.
    # origin_access_identity is required for s3 origins. This manages CloudFront access to the S3 bucket.
    # We do not want to create an origin_access_identity for non-s3 origins. We also do not want our S3 buckets to be public.
    def s3_origin_access_identity(origin_domain: str):
        if "s3" in self.origin_domain:
            self.origin_access_identity = aws.cloudfront.OriginAccessIdentity(f"{name}-origin-access-identity",
                                                                              opts=pulumi.ResourceOptions(parent=self))
        else:
            self.origin_access_identity = None
        return self.origin_access_identity

    def dns(self, stack):
        #print(f"args passed to dns: {self} | {name} | {stack} | {kwargs} \n")
        #print("=======================================================\n")
        #for attr in dir(self):
            #print(f"attr: {attr}\n")
        full_name = self.kwargs.get('fqdn')
        zone_id = self.kwargs.get('zone_id', 'b4b7fec0d0aacbd55c5a259d1e64fff5')
        #lb_dns_name = self.kwargs.get('load_balancer_dns_name',
                                      #self.load_balancer.load_balancer.dns_name)  # pragma: no cover
        #cloudfront_domain_name = kwargs.get('cloudfront_domain_name',
                                                #self.distribution.domain_name)
        pulumi.export("url", Output.concat("https://", full_name))

        self.cert = aws.acm.Certificate(
            "cert",
            domain_name=full_name,
            validation_method="DNS",
            #tags=self.tags,
            tags=self.kwargs.get('tags'),
            opts=pulumi.ResourceOptions(parent=self),
        )
        domain_validation_options = self.kwargs.get('domain_validation_options',
                                                    self.cert.domain_validation_options)  # pragma: no cover

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
            opts=pulumi.ResourceOptions(parent=self, depends_on=[self.cert_validation_record]),
        )










