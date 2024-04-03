from enum import Enum
import pulumi
import pulumi_aws as aws
from typing import List, Optional, Sequence
from strongmind_deployment.subnet import SubnetSpec, SubnetType


class NatGatewayStrategy(str, Enum):
    SINGLE = "single"
    ONE_PER_AZ = "one_per_az"
    NONE = "none"

    def __str__(self):
        return self.value


class VpcComponentArgs:
    def __init__(
        self,
        cidr_block: str,
        nat_gateway_strategy: Optional[NatGatewayStrategy] = NatGatewayStrategy.SINGLE,
    ):
        self.cidr_block = cidr_block
        self.nat_gateway_strategy = nat_gateway_strategy


class SubnetWithLocation:
    def __init__(self, subnet: aws.ec2.Subnet, availability_zone: str):
        self.subnet = subnet
        self.availability_zone = availability_zone


class VpcComponent(pulumi.ComponentResource):
    public_subnets: List[aws.ec2.Subnet] = []
    private_subnets: List[aws.ec2.Subnet] = []
    database_subnets: List[aws.ec2.Subnet] = []

    def __init__(self, name, args: VpcComponentArgs, opts=None):
        super().__init__("strongmind:global_build:commons:vpc", name, {}, opts)
        self.child_opts = pulumi.ResourceOptions(parent=self)
        self.vpc_name = name
        self.subnet_specs = SubnetSpec.get_standard_subnet_specs(args.cidr_block)
        self.args: VpcComponentArgs = args
        self.azs = aws.get_availability_zones(state="available").names[:3]
        self.validate_args()
        self.create_resources()

    def validate_args(self):
        """
        Basic validation to ensure we are setting things up correctly.
        """
        # ensure there are 3 AZ's
        if len(self.azs) != 3:
            raise ValueError(
                "This module requires exactly 3 availability zones. The region you are deploying to does not have 3 AZ's available."
            )

        # CIDR is required to be a /16
        if not self.args.cidr_block.endswith("/16"):
            raise ValueError("VPC CIDR must be a /16")

    def create_resources(self):
        self.vpc = self.create_vpc()
        self.gateway = self.create_internet_gateway()

        self.public_subnets = self.create_public_subnets()
        self.private_subnets = self.create_private_subnets()
        self.database_subnets = self.create_database_subnets()
        self.create_vpc_endpoints()

    def create_vpc(self: pulumi.ComponentResource):
        vpc_name = self.vpc_name

        return aws.ec2.Vpc(
            vpc_name,
            cidr_block=self.args.cidr_block,
            enable_dns_hostnames=True,
            enable_dns_support=True,
            tags={"Name": vpc_name},
            opts=self.child_opts,
        )

    def create_internet_gateway(self) -> aws.ec2.InternetGateway:
        return aws.ec2.InternetGateway(
            f"{self.vpc_name}-igw",
            vpc_id=self.vpc.id,
            tags={"Name": f"{self.vpc_name}-gateway"},
            opts=self.child_opts,
        )

    def should_create_nat_gateway(self, i: int) -> bool:
        """
        Expects the index of an iterator to determine if a NAT Gateway should be created.
        """
        if self.args.nat_gateway_strategy == NatGatewayStrategy.ONE_PER_AZ:
            return True

        return self.args.nat_gateway_strategy == NatGatewayStrategy.SINGLE and i == 0

    def create_public_subnets(self):
        public_subnets = []

        public_subnet_spec = SubnetSpec.get_subnet_by_type(
            self.subnet_specs, SubnetType.PUBLIC
        )

        subnet_azs = zip(public_subnet_spec.cidr_blocks, self.azs)

        for cidr_block, az in subnet_azs:
            public_subnet = aws.ec2.Subnet(
                f"pub-subnet-{az}",
                vpc_id=self.vpc.id,
                cidr_block=cidr_block,
                map_public_ip_on_launch=True,
                availability_zone=az,
                tags={
                    "Name": f"{self.vpc_name}-public-subnet-{az}",
                    "SubnetType": SubnetType.PUBLIC,
                },
                opts=self.child_opts,
            )
            public_route_table = aws.ec2.RouteTable(
                f"pub-routeTable-{az}",
                vpc_id=self.vpc.id,
                routes=[
                    aws.ec2.RouteTableRouteArgs(
                        cidr_block="0.0.0.0/0", gateway_id=self.gateway.id
                    ),
                ],
                tags={
                    "Name": f"{self.vpc_name}-public-rt-{az}",
                    "SubnetType": SubnetType.PUBLIC,
                },
                opts=self.child_opts,
            )

            aws.ec2.RouteTableAssociation(
                f"pub-routeTableAssociation-{az}",
                subnet_id=public_subnet.id,
                route_table_id=public_route_table.id,
                opts=self.child_opts,
            )

            public_subnets.append(public_subnet)
            self.public_subnets = public_subnets

    def create_private_subnets(self):
        private_subnets = []
        recently_created_nat_gateway: aws.ec2.NatGateway = None

        private_subnet_spec = SubnetSpec.get_subnet_by_type(
            self.subnet_specs, SubnetType.PRIVATE
        )

        subnet_azs = zip(private_subnet_spec.cidr_blocks, self.azs)

        for i, (cidr_block, az) in enumerate(subnet_azs):
            private_subnet = aws.ec2.Subnet(
                f"pri-subnet-{az}",
                vpc_id=self.vpc.id,
                cidr_block=cidr_block,
                map_public_ip_on_launch=False,
                availability_zone=az,
                tags={
                    "Name": f"{self.vpc_name}-private-subnet-{az}",
                    "SubnetType": SubnetType.PRIVATE,
                },
                opts=self.child_opts,
            )

            if self.should_create_nat_gateway(i):
                # If we are in a single nat gateawy scenario, only the first AZ will get one.
                # However, this property will persist outside the for loop, and be assigned
                # to other Subnets.
                # get the public subnet for the same AZ
                public_subnet_id = self.get_subnet_in_az(
                    self.vpc.id, SubnetType.PUBLIC, az
                )
                recently_created_nat_gateway = self.create_nat_gateway(
                    az=az,
                    public_subnet_id=public_subnet_id,
                )

            if not self.args.nat_gateway_strategy == NatGatewayStrategy.NONE:
                private_route_table = aws.ec2.RouteTable(
                    f"pri-routeTable-{az}",
                    vpc_id=self.vpc.id,
                    routes=[
                        aws.ec2.RouteTableRouteArgs(
                            cidr_block="0.0.0.0/0",
                            nat_gateway_id=recently_created_nat_gateway.id,
                        ),
                    ],
                    tags={
                        "Name": f"{self.vpc_name}-private-rt-{az}",
                        "SubnetType": SubnetType.PRIVATE,
                    },
                    opts=self.child_opts,
                )

                aws.ec2.RouteTableAssociation(
                    f"pri-routeTableAssociation-{az}",
                    subnet_id=private_subnet.id,
                    route_table_id=private_route_table.id,
                    opts=self.child_opts,
                )

            private_subnets.append(private_subnet.id)
        return private_subnets

    def create_nat_gateway(self, az, public_subnet_id):
        eip = aws.ec2.Eip(
            f"{self.vpc_name}-eip-{az}",
            tags={"Name": f"{self.vpc_name}-natgateway-eip-{az}"},
            opts=self.child_opts,
        )

        nat_gateway = aws.ec2.NatGateway(
            f"{self.vpc_name}-natGateway-{az}",
            subnet_id=public_subnet_id,
            allocation_id=eip.id,
            tags={
                "Name": f"{self.vpc_name}-nat-gateway-{az}",
            },
            opts=self.child_opts,
        )
      
        return nat_gateway

    def create_database_subnets(self):
        database_subnets = []

        public_subnet_spec = SubnetSpec.get_subnet_by_type(
            self.subnet_specs, SubnetType.ISOLATED
        )

        subnet_azs = zip(public_subnet_spec.cidr_blocks, self.azs)

        for cidr_block, az in subnet_azs:
            database_subnet = aws.ec2.Subnet(
                f"db-subnet-{az}",
                vpc_id=self.vpc.id,
                cidr_block=cidr_block,
                map_public_ip_on_launch=False,
                availability_zone=az,
                tags={
                    "Name": f"{self.vpc_name}-database-subnet-{az}",
                    "SubnetType": SubnetType.ISOLATED,
                },
                opts=self.child_opts,
            )
            database_subnets.append(database_subnet.id)
        return database_subnets

    def create_vpc_endpoints(self):
        self.create_private_link_interface("ecr.api")
        self.create_private_link_interface("ecr.dkr")
        self.create_private_link_interface("logs")
        self.create_private_link_interface("dms", SubnetType.ISOLATED)
        self.create_private_link_interface("secretsmanager")
        self.create_private_link_gateway("s3")

    def create_private_link_gateway(self, service_name: str):
        region = aws.get_region().name
        aws.ec2.VpcEndpoint(
            f"{service_name}-gateway",
            vpc_id=self.vpc.id,
            service_name=f"com.amazonaws.{region}.{service_name}",
            vpc_endpoint_type="Gateway",
            tags={
                "Name": f"{service_name}-gateway",
            },
        )

    def create_private_link_interface(
        self,
        service_name: str,
        subnet_type: SubnetType = SubnetType.PRIVATE,
    ):
        region = aws.get_region().name
        target_subnet_ids = self.get_subnets(self.vpc.id, subnet_type)
        aws.ec2.VpcEndpoint(
            f"{service_name}-interface",
            vpc_id=self.vpc.id,
            service_name=f"com.amazonaws.{region}.{service_name}",
            vpc_endpoint_type="Interface",
            # security_group_ids=[self.vpc.default_security_group_id],
            subnet_ids=target_subnet_ids,
            private_dns_enabled=True,
            opts=self.child_opts,
            tags={
                "Name": f"{service_name}-interface",
            },
        )

    @staticmethod
    def get_subnets(vpc_id: str, placement: SubnetType) -> Sequence[str]:
        """
        Get the subnet ids for a given subnet type.
        """
        subnets_result: aws.ec2.AwaitableGetSubnetsResult = aws.ec2.get_subnets(
            filters=[
                aws.ec2.GetSubnetsFilterArgs(
                    name="vpc-id",
                    values=[vpc_id],
                ),
                aws.ec2.GetSubnetsFilterArgs(
                    name="tag:SubnetType",
                    values=[placement],
                ),
            ]
        )

        return subnets_result.ids

    @staticmethod
    def get_subnet_in_az(vpc_id: str, placement: SubnetType, az: str) -> str:
        """
        Get the subnet id for a given subnet type and availability zone.
        """
        subnets_result: aws.ec2.AwaitableGetSubnetsResult = aws.ec2.get_subnets(
            filters=[
                aws.ec2.GetSubnetsFilterArgs(
                    name="vpc-id",
                    values=[vpc_id],
                ),
                aws.ec2.GetSubnetsFilterArgs(
                    name="tag:SubnetType",
                    values=[placement],
                ),
                aws.ec2.GetSubnetsFilterArgs(
                    name="availability-zone",
                    values=[az],
                ),
            ]
        )
        return subnets_result.ids[0]
