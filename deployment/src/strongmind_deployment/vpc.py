from dataclasses import dataclass
from typing import Optional
import typing
import pulumi
import pulumi_awsx as awsx
from pulumi_awsx.ec2 import SubnetSpecArgs


# @dataclass
# class VpcComponentArgs:
#     vpc_name: str
#     cidr_block: str
#     tags: Optional[dict] = None
#     enable_nat_gateway: bool = False

class VpcComponentArgs:
    def __init__(
        self,
        vpc_name: str,
        cidr_block: str,
        tags: Optional[dict] = None,
        enable_nat_gateway: bool = False,
    ) -> None:
        self.vpc_name = vpc_name or f"{pulumi.get_project()}-{pulumi.get_stack()}"
        self.cidr_block = cidr_block
        self.tags = tags
        self.enable_nat_gateway = enable_nat_gateway

class VpcComponent(pulumi.ComponentResource):
    def __init__(self, args: VpcComponentArgs) -> None:
        self.args = args
        self.create_resources()

    @property
    def id(self) -> str:
        return self.vpc.vpc_id.apply(lambda id: id)

    def create_resources(self) -> None:
        self.vpc = self.create_vpc()

    def get_vpc_cidr_prefix(self) -> str:
        cidr_prefix = self.args.cidr_block.split(".")[:2]
        return ".".join(cidr_prefix)

    def create_vpc(self) -> awsx.ec2.Vpc:
        nat_gateway_config = self.get_nat_gateway_config()

        cidr_prefix = self.get_vpc_cidr_prefix()

        subnet_specs = [
            SubnetSpecArgs(
                type=awsx.ec2.SubnetType.PRIVATE,
                cidr_mask=19,
                cidr_blocks=[
                    f"{cidr_prefix}.0.0/19",
                    f"{cidr_prefix}.64.0/19",
                    f"{cidr_prefix}.128.0/19",
                ],
            ),
            SubnetSpecArgs(
                type=awsx.ec2.SubnetType.PUBLIC,
                cidr_mask=20,
                cidr_blocks=[
                    f"{cidr_prefix}.32.0/20",
                    f"{cidr_prefix}.96.0/20",
                    f"{cidr_prefix}.160.0/20",
                ],
            ),
            SubnetSpecArgs(
                type=awsx.ec2.SubnetType.ISOLATED,
                cidr_mask=21,
                cidr_blocks=[
                    f"{cidr_prefix}.48.0/21",
                    f"{cidr_prefix}.112.0/21",
                    f"{cidr_prefix}.176.0/21",
                ],
            ),
            # must explicitly define remaining cidrs
            SubnetSpecArgs(
                type=awsx.ec2.SubnetType.UNUSED,
                cidr_mask=21,
                cidr_blocks=[
                    f"{cidr_prefix}.56.0/21",
                    f"{cidr_prefix}.120.0/21",
                    f"{cidr_prefix}.184.0/21",
                    # f"{cidr_prefix}.192.0/18",
                ],
            ),
            SubnetSpecArgs(
                type=awsx.ec2.SubnetType.UNUSED,
                cidr_blocks=[
                    f"{cidr_prefix}.192.0/19",
                    f"{cidr_prefix}.224.0/20",
                    f"{cidr_prefix}.240.0/20",
                ],
            ),
        ]

        vpc = awsx.ec2.Vpc(
            f"{self.args.vpc_name}",
            cidr_block=self.args.cidr_block,
            number_of_availability_zones=3,
            enable_dns_hostnames=True,
            enable_dns_support=True,
            nat_gateways=nat_gateway_config,
            subnet_specs=subnet_specs,
            subnet_strategy=awsx.ec2.SubnetAllocationStrategy.AUTO,
            tags=self.args.tags,
        )

        # TODO: wip - create a class property for each subnet and AZ so they can be referenced specifically.
        # can probably use the pulumi filters for this.
        # subnet: aws.ec2.Subnet
        # for subnet in enumerate(vpc.subnets):
        #     setattr(self, f"public_subnet_{subnet.availability_zone}", subnet)

        return vpc

    def get_nat_gateway_config(self) -> awsx.ec2.NatGatewayConfigurationArgs:
        if not self.args.enable_nat_gateway:
            return awsx.ec2.NatGatewayConfigurationArgs(
                strategy=awsx.ec2.NatGatewayStrategy.NONE
            )

        # if the stack doesn't contain 'prod' then use a single NAT gateway
        if "prod" in pulumi.get_stack():
            strategy = awsx.ec2.NatGatewayStrategy.ONE_PER_AZ
        else:
            strategy = awsx.ec2.NatGatewayStrategy.SINGLE

        config_args = awsx.ec2.NatGatewayConfigurationArgs(strategy=strategy)
        return config_args
