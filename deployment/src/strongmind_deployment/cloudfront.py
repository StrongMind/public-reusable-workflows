import pulumi
import pulumi_aws as aws

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
    def __init__(self,name, *args, **kwargs):

        super().__init__("custom:module:DistributionComponent", name, {})
        self._transformations = []
        #self.__dict__.update(kwargs)
        #opts: Optional[pulumi.ResourceOptions] = None):
        print(f"args passed to DistributionComponent: {args} and kwargs passed to DistributionComponent: {kwargs}\n")

        origin_domain = kwargs.get('origin_domain')
        origin_id = f"{name}-origin"
        aws_cloudfront_origin_access_identity = {
            "identity": {
        "cloudfront_access_identity_path": f"{origin_id}-origin-access-identity"
        }
    }
        aws_cloudfront_origin_access_identity = aws.cloudfront.OriginAccessIdentity(f"{origin_id}-myOriginAccessIdentity",
        comment="")

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

