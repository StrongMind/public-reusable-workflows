import pulumi
import pulumi_aws as aws
from pulumi import Output
import re
import os
import ipaddress

class VpcComponent(pulumi.ComponentResource):
    def __init__(self, name, **kwargs):
        super().__init__("custom:module:VPC", name, {})
        self.kwargs = kwargs
        self.name = name
        self.stack = kwargs.get('stack')
        self.cidr = kwargs.get('cidr')
        try:
            self.cidr_ending = int(self.cidr.split('/')[-1])
        except:
            raise ValueError("Invalid CIDR block")
        self.public_subnets, self.private_subnets = self.split_cidr(self.cidr)
        self.public_subnets_number = kwargs.get('public_subnets_number', len(self.public_subnets))
        self.private_subnets_number = kwargs.get('private_subnets_number', len(self.private_subnets))
        self.enable_dns_support = kwargs.get('enable_dns_support', True)
        self.enable_dns_hostnames = kwargs.get('enable_dns_hostnames', True)
        self.availability_zones = kwargs.get('availability_zones', ['us-west-2a', 'us-west-2b', 'us-west-2c'])
        self.env_name = os.environ.get('ENVIRONMENT_NAME', 'stage')
        project = pulumi.get_project()
        stack = pulumi.get_stack()
        with open('../CODEOWNERS', 'r') as file:
            owning_team = [line.strip().split('@')[-1] for line in file if '@' in line][-1].split('/')[1]

        tags = {
            "product": project,
            "repository": project,
            "service": project,
            "environment": self.env_name,
            "owner": owning_team,
        }

        def standard_tags(extra_tags:dict):
            return {
                "product": project,
                "repository": project,
                "service": project,
                "environment": self.env_name,
                "owner": owning_team,
                **extra_tags,
            }

        tag = tags.copy()
        tag["Name"] = f"{name}-vpc"
        self.vpc = aws.ec2.Vpc(f"{name}-vpc",
            cidr_block=self.cidr,
            enable_dns_hostnames=self.enable_dns_hostnames,
            enable_dns_support=self.enable_dns_support,
            tags=standard_tags({"Name": f"{name}-vpc"}),
        )

        self.internet_gateway = aws.ec2.InternetGateway(f"{name}-igw",
            vpc_id=self.vpc.id,
            tags=standard_tags({"Name": f"{name}-igw"}),
            )

        def create_nat_gateway(az, public_subnet_id):
            eip = aws.ec2.Eip(
                f"{self.name}-eip-{az}",
                tags={"Name": f"{self.name}-natgateway-eip-{az}"},
            )

            nat_gateway = aws.ec2.NatGateway(
                f"{self.name}-natGateway-{az}",
                subnet_id=public_subnet_id,
                allocation_id=eip.id,
                tags={
                    "Name": f"{self.name}-nat-gateway-{az}",
                },
            )

            return nat_gateway

        self.public_route_table = aws.ec2.RouteTable(f"{name}-public-rt",
                                              vpc_id=self.vpc.id,
                                              opts=pulumi.ResourceOptions(depends_on=[self.vpc]),
                                              routes=[aws.ec2.RouteTableRouteArgs(
                                                  cidr_block="0.0.0.0/0",
                                                  gateway_id=self.internet_gateway.id,
                                              )
                                              ],
                                              tags=standard_tags({"Name": f"{name}-public-rt"}),
                                              )
        def create_private_route_table(nat_gateway, i):
            private_route_table = aws.ec2.RouteTable(f"{name}-private-rt-{i}",
                                                vpc_id=self.vpc.id,
                                                opts=pulumi.ResourceOptions(depends_on=[self.vpc]),
                                                routes=[aws.ec2.RouteTableRouteArgs(
                                                    cidr_block="0.0.0.0/0",
                                                    nat_gateway_id=nat_gateway.id,
                                                )
                                                ],
                                                tags=standard_tags({"Name": f"{name}-private-rt-{i}"}),
                                                )
            return private_route_table

        # Create public subnets
        public_subnets = []
        for i in range(self.public_subnets_number):
            public_subnet = aws.ec2.Subnet(
                f"{name}-public-{i}",
                vpc_id=self.vpc.id,
                cidr_block=self.public_subnets[i],
                availability_zone=self.availability_zones[i],
                tags=standard_tags({"Name": f"{name}-public-{i}"}),
            )
            public_subnets.append(public_subnet)

            aws.ec2.RouteTableAssociation(f"{name}-public-rt-assoc-{i}",
                                          route_table_id=self.public_route_table.id,
                                          subnet_id=public_subnet.id,
                                          opts=pulumi.ResourceOptions(depends_on=[self.public_route_table, public_subnet]))

        nat_gateways = []
        for i, public_subnet in enumerate(public_subnets):
            nat_gateway = create_nat_gateway(self.availability_zones[i], public_subnet.id)
            nat_gateways.append(nat_gateway)

        for i in range(self.private_subnets_number):
            private_subnet = aws.ec2.Subnet(f"{name}-private-{i}",
                vpc_id=self.vpc.id,
                cidr_block=f"{self.private_subnets[i]}",
                availability_zone=f"{self.availability_zones[i]}",
                tags=standard_tags({"Name": f"{name}-private-{i}"}),
            )
            self.private_subnets.append(private_subnet)
            nat_gateway = nat_gateways[i % len(nat_gateways)]
            private_route_table = create_private_route_table(nat_gateway, i)
            aws.ec2.RouteTableAssociation(f"{name}-private-rt-assoc-{i}",
                                            route_table_id=private_route_table.id,
                                            subnet_id=private_subnet.id,
                                            opts=pulumi.ResourceOptions(depends_on=[private_route_table, private_subnet]))




    def split_cidr(self,cidr):
        print(cidr)
        try:
            network = ipaddress.ip_network(cidr)
        except ValueError:
            print("Invalid CIDR notation")

        if network.num_addresses % 2 != 0:
            print("CIDR network size is not divisible by 2")

        subnets = list(network.subnets(prefixlen_diff=2))

        public_subnets = [str(subnet) for subnet in subnets[:2]]
        private_subnets = [str(subnet) for subnet in subnets[2:]]
        print(f"networks are {public_subnets} and {private_subnets}")

        return public_subnets, private_subnets
