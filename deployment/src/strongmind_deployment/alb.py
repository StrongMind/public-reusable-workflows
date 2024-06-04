from enum import Enum
from typing import Optional, Sequence
import pulumi
import pulumi_aws as aws
import pulumi_aws.ec2 as ec2
import pulumi_aws.lb as lb
from strongmind_deployment.util import get_project_stack
from strongmind_deployment import vpc


class AlbPlacement(str, Enum):
    INTERNAL = "internal"
    EXTERNAL = "external"

    def __str__(self):
        return str(self.value)


class AlbArgs:
    """

    vpc_id: str - the VPC ID where the ALB will be created.  This VPC requires subnets to be tagged by the vpc.SubnetType enum.
    certificate_arn: str - the ARN of the ACM certificate to use for the HTTPS listener.
    placement: AlbPlacement - the placement of the ALB.  Either internal or external.
    internal_ingress_cidrs: list[str] - a list of CIDR blocks that are allowed to access the ALB when the placement is internal.
    ingress_sg: ec2.SecurityGroup - a security group that is allowed to access the ALB.
    should_protect: bool - whether or not to enable deletion protection on the ALB.  Defaults to False.  You should set this for production stacks.
    """
    def __init__(
        self,
        vpc_id: str,
        certificate_arn: str,
        placement: Optional[AlbPlacement] = AlbPlacement.EXTERNAL,
        internal_ingress_cidrs: list[str] = [],
        ingress_sg: ec2.SecurityGroup = None,
        should_protect: bool = False,
    ):
        self.vpc_id = vpc_id
        self.certificate_arn = certificate_arn
        self.placement = placement or AlbPlacement.EXTERNAL
        self.internal_ingress_cidrs = internal_ingress_cidrs
        self.ingress_sg = ingress_sg
        self.should_protect = should_protect


class Alb(pulumi.ComponentResource):
    """
    Represents an Application Load balancer with a HTTPS listener and a port 80 redirect listener.

    """
    alb: lb.LoadBalancer
    https_listener: lb.Listener
    security_group: ec2.SecurityGroup

    def __init__(self, name: str, args: AlbArgs, opts=None):
        super().__init__("strongmind:global_build:commons:alb", name, {}, opts)

        self.args = args
        self.is_internal = args.placement == AlbPlacement.INTERNAL
        self.subnet_placement: vpc.SubnetType = vpc.SubnetType.PRIVATE if self.is_internal else vpc.SubnetType.PUBLIC
        self.subnet_ids: Sequence[str] = vpc.VpcComponent.get_subnets(vpc_id=args.vpc_id, placement=args.placement)
        self.project_stack = get_project_stack()

        self.child_opts = pulumi.ResourceOptions(parent=self)
        self.create_resources()

    def create_resources(self):
        self.alb = self.create_loadbalancer()
        self.https_listener = self.create_https_listener()
        self.create_port_80_redirect_listener()

    def create_loadbalancer(self)-> lb.LoadBalancer:

        alb_security_group = ec2.SecurityGroup(
            f"{self.project_stack}-alb_sg",
            description=f"Load Balancer Security Group for {self.args.placement} ALB",
            vpc_id=self.args.vpc_id,
            tags={
                "Name": "allow_tls",
            },
            opts=self.child_opts,
        )

        # this is a side effect - refactor out of this function
        self.security_group = alb_security_group

        ec2.SecurityGroupRule(
            "alb_default_egress_rule",
            type="egress",
            from_port=0,
            to_port=0,
            protocol="-1",
            cidr_blocks=["0.0.0.0/0"],
            security_group_id=alb_security_group.id,
        )

        self.add_ingress_rules_to_security_group(security_group=alb_security_group)

        alb = lb.LoadBalancer(
            self.project_stack[:30],
            internal=self.is_internal,
            load_balancer_type="application",
            security_groups=[alb_security_group.id],
            subnets=self.subnet_ids,
            enable_deletion_protection=self.args.should_protect,
            opts=self.child_opts,
        )
        return alb

    def create_https_listener(self):
        """
        Create an HTTPS listener for the ALB.  This listener will return a 404 response for any request.
        Use this listener to create additional listeners connected to their target groups.
        """
        https_listener = lb.Listener(
            f"{self.project_stack}-https-listener",
            load_balancer_arn=self.alb.arn,
            port=443,
            certificate_arn=self.args.certificate_arn,
            protocol="HTTPS",
            default_actions=[
                lb.ListenerDefaultActionArgs(
                    type="fixed-response",
                    fixed_response=lb.ListenerDefaultActionFixedResponseArgs(
                        content_type="text/plain",
                        message_body="Path Not Found",
                        status_code="404",
                    ),
                )
            ],
            opts=self.child_opts,
        )
        return https_listener

    def create_port_80_redirect_listener(self):
        """
        Create a listener that redirects all requests on port 80 to the HTTPS listener.
        """
        port_80_redirect_listener = aws.alb.Listener(
            f"{self.project_stack}-80-redirect-443",
            load_balancer_arn=self.alb.arn,
            port=80,
            default_actions=[
                {
                    "type": "redirect",
                    "redirect": {
                        "port": "443",
                        "protocol": "HTTPS",
                        "status_code": "HTTP_301",
                        "host": "#{host}",
                        "path": "/#{path}",
                        "query": "#{query}",
                    },
                }
            ],
        )
        return port_80_redirect_listener

    def add_ingress_rules_to_security_group(self, security_group: ec2.SecurityGroup):
        """
        Allow ingress from the supplied security group to the ALB.
        """
        # TODO: for internal placment, we must allow ingress from the VPC CIDR block.
        # currently this isn't required, so it is not implemented.
        if self.args.ingress_sg:
            ec2.SecurityGroupRule(
                description=f"Ingress from sg {self.args.ingress_sg.id}",
                from_port=0,
                to_port=0,
                protocol="-1",
                security_groups=[self.args.ingress_sg.id],
            )

        if not self.is_internal:
            ec2.SecurityGroupRule(
                "tls_ingress",
                description="TLS internet",
                type="ingress",
                from_port=443,
                to_port=443,
                protocol="tcp",
                cidr_blocks=[
                    "0.0.0.0/0",
                ],
                security_group_id=security_group.id,
            )
            ec2.SecurityGroupRule(
                "http_ingress",
                description="Internet",
                type="ingress",
                from_port=80,
                to_port=80,
                protocol="tcp",
                cidr_blocks=[
                    "0.0.0.0/0",
                ],
                security_group_id=security_group.id,
            )
