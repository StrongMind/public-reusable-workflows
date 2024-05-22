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
        self.enable_internet_gateway = kwargs.get('enable_internet_gateway', False)
        self.availability_zones = kwargs.get('availability_zones', ['us-west-2a', 'us-west-2b', 'us-west-2c'])
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

        self.vpc = aws.ec2.Vpc(f"{name}-vpc",
            cidr_block=self.cidr,
            enable_dns_hostnames=self.enable_dns_hostnames,
            enable_dns_support=self.enable_dns_support,
            tags=self.tags,
        )

        for i in range(self.private_subnets_number):
            self.private_subnets.append(aws.ec2.Subnet(f"{name}-private-{i}",
                vpc_id=self.vpc.id,
                cidr_block=f"{self.private_subnets[i]}",
                availability_zone=f"{self.availability_zones[i]}",
                tags=self.tags,
            ))
        for i in range(self.public_subnets_number):
            self.public_subnets.append(aws.ec2.Subnet(f"{name}-public-{i}",
                vpc_id=self.vpc.id,
                cidr_block=f"{self.public_subnets[i]}",
                availability_zone=f"{self.availability_zones[i]}",
                tags=self.tags,
            ))
        if self.enable_internet_gateway:
            self.internet_gateway = aws.ec2.InternetGateway(f"{name}-igw",
                vpc_id=self.vpc.id,
                tags=self.tags,
            )
        else:
            self.internet_gateway = None
            
        vpc_cidr_block = Output.concat(self.vpc.cidr_block)
        vpc_endpoint_id = Output.concat(self.vpc.default_network_acl_id)

        self.route_table = aws.ec2.RouteTable(f"{name}-rt-pulumi",
            vpc_id=self.vpc.id,
            opts=pulumi.ResourceOptions(depends_on=[self.vpc]),
            routes=[aws.ec2.RouteTableRouteArgs(
                cidr_block=vpc_cidr_block,
                gateway_id=self.internet_gateway.id if self.internet_gateway else vpc_endpoint_id,
            )
            ],
            tags=self.tags,
        )


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
