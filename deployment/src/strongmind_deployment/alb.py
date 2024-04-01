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


class AlbArgs():
    def __init__(
        self,
        vpc_id: str,
        certificate_arn: str,
        subnet_placement: Optional[AlbPlacement] = AlbPlacement.EXTERNAL,
        internal_ingress_cidrs: list[str] = [],
        ingress_sg: ec2.SecurityGroup = None,
        should_protect: bool = False
    ):
        self.vpc_id = vpc_id
        self.certificate_arn = certificate_arn
        self.subnet_placement = subnet_placement or AlbPlacement.EXTERNAL
        self.internal_ingress_cidrs = internal_ingress_cidrs
        self.ingress_sg = ingress_sg
        self.should_protect = should_protect


class Alb(pulumi.ComponentResource):
    alb: lb.LoadBalancer
    https_listener: lb.Listener

    def __init__(self, name: str, args: AlbArgs, opts=None):
        super().__init__("strongmind:global_build:commons:alb", name, {}, opts)

        self.args = args
        self.is_internal = args.subnet_placement == AlbPlacement.INTERNAL
        self.subnet_ids: Sequence[str]= vpc.VpcComponent.get_subnets(
            vpc_id=args.vpc_id, placement=args.subnet_placement
        )
        self.project_stack = get_project_stack()
        
        self.child_opts = pulumi.ResourceOptions(parent=self)
        self.create_resources()
    
    def create_resources(self):
        self.alb = self.create_loadbalancer()
        self.https_listener = self.create_https_listener()
        self.create_port_80_redirect_listener()
                        
    def create_loadbalancer(self):
        specific_ingress_rules = self.create_ingress_rules()
        alb_default_security_group = ec2.SecurityGroup(
            f"{self.project_stack}-alb_sg",
            description=f"Load Balancer Security Group for {self.args.subnet_placement} ALB",
            vpc_id=self.args.vpc_id,
            ingress=specific_ingress_rules,
            egress=[
                ec2.SecurityGroupEgressArgs(
                    from_port=0,
                    to_port=0,
                    protocol="-1",
                    cidr_blocks=["0.0.0.0/0"],
                )
            ],
            tags={
                "Name": "allow_tls",
            },
            opts=self.child_opts,
        )

        # TODO: implement feature toggle for access logs
        # create access logs bucket in the account and send access logs there.
        # access_logs_bucket_name = self.account_stack.get_output(....

        alb = lb.LoadBalancer(
            self.project_stack[:30],
            internal=self.is_internal,
            load_balancer_type="application",
            security_groups=[alb_default_security_group.id],
            subnets=self.subnet_ids,
            enable_deletion_protection=self.args.should_protect,
            # access_logs=aws.lb.LoadBalancerAccessLogsArgs(
            #     bucket=access_logs_bucket_name,
            #     prefix=f"{self.stack}-ialb",
            #     enabled=True,
            # ),
            opts=self.child_opts,
        )
        return alb

    def create_https_listener(self):
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

    def create_ingress_rules(self):
        ingress_sg = None
        if self.args.ingress_sg:
            ingress_sg = ec2.SecurityGroupIngressArgs(
                description="Group Ingress",
                from_port=0,
                to_port=0,
                protocol="-1",
                security_groups=[self.args.ingress_sg.id],
            )

        rules: list[ec2.SecurityGroupIngressArgs] = []

        if self.args.subnet_placement == AlbPlacement.EXTERNAL:
            rules = [
                ec2.SecurityGroupIngressArgs(
                    description="TLS internet",
                    from_port=443,
                    to_port=443,
                    protocol="tcp",
                    cidr_blocks=[
                        "0.0.0.0/0",
                    ],
                ),
                ec2.SecurityGroupIngressArgs(
                    description="Internet",
                    from_port=80,
                    to_port=80,
                    protocol="tcp",
                    cidr_blocks=[
                        "0.0.0.0/0",
                    ],
                ),
            ]
        else:
            rules = [
                ec2.SecurityGroupIngressArgs(
                    description="ingress",
                    from_port=0,
                    to_port=65535,
                    protocol="tcp",
                    cidr_blocks=self.args.internal_ingress_cidrs,
                ),
            ]

        #TODO: continue refactoring this create_ingress_rules function, it's confusing, as it's doing two things.
        if ingress_sg:
            rules.append(ingress_sg)

        return rules

    