from enum import Enum
from typing import Optional, Dict
import pulumi
import pulumi_aws as aws


class Route53ZoneArgs:
    def __init__(
        self,
        domain_name: str,
        vpc_id: Optional[str] = None,
        vpc_region: Optional[str] = None,
        comment: Optional[str] = "Managed by Pulumi",
        force_destroy: Optional[bool] = False,
        delegation_set_id: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
    ):
        self.domain_name = domain_name
        self.vpc_id = vpc_id
        self.vpc_region = vpc_region
        self.comment = comment
        self.force_destroy = force_destroy
        self.delegation_set_id = delegation_set_id
        self.tags = tags


class R53ZoneExportNames(str, Enum):
    ROUTE53_ZONE_ID = "zone_id"
    ROUTE53_ZONE_NAME = "zone_name"
    ROUTE53_ZONE_ARN = "zone_arn"
    ROUTE53_ZONE_DNS_SERVERS = "dns_servers"

    def __str__(self):
        return self.value


class Route53Zone(pulumi.ComponentResource):
    zone: aws.route53.Zone
    domain_name: str

    def __init__(self, name, args: Route53ZoneArgs, opts=None):
        super().__init__("strongmind:global_build:commons:route53zone", name, {}, opts)
        child_opts = pulumi.ResourceOptions(parent=self)

        if args.vpc_id is not None:
            self.zone = self.create_private_zone(args, child_opts)
        else:
            self.zone = self.create_public_zone(args, child_opts)

        self.domain_name = args.domain_name

    def create_public_zone(
        self: pulumi.ComponentResource,
        args: Route53ZoneArgs,
        opts: pulumi.ResourceOptions,
    ):
        zone = aws.route53.Zone(
            f"{args.domain_name}",
            name=args.domain_name,
            comment=args.comment,
            delegation_set_id=args.delegation_set_id,
            force_destroy=args.force_destroy,
            tags=args.tags,
            opts=opts,
        )

        return zone

    def create_private_zone(
        self: pulumi.ComponentResource,
        args: Route53ZoneArgs,
        opts: pulumi.ResourceOptions,
    ):
        zone = aws.route53.Zone(
            f"{args.domain_name}",
            name=args.domain_name,
            comment=args.comment,
            vpcs=[
                aws.route53.ZoneVpcArgs(vpc_id=args.vpc_id, vpc_region=args.vpc_region)
            ],
            force_destroy=args.force_destroy,
            tags=args.tags,
            opts=opts,
        )

        return zone
