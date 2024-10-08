from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock
import pulumi
import pulumi_aws as aws
import pulumi_aws.ecs
from pulumi_aws.ecs import ServiceNetworkConfigurationArgs


def get_pulumi_mocks(faker, fake_password=None, secret_string="{}"):
    class PulumiMocks(pulumi.runtime.Mocks):
        def __init__(self):
            super().__init__()
            self.fake_password = fake_password

        def new_resource(self, args: pulumi.runtime.MockResourceArgs):
            outputs = args.inputs
            if args.typ == "awsx:ecr:Repository":
                outputs = {
                    **args.inputs,
                    "url": f"{faker.word()}.dkr.ecr.us-west-2.amazonaws.com",
                    "force_delete": args.inputs["forceDelete"],
                }
            if args.typ == "awsx:ecs:FargateService":
                class TaskDefinitionMock(dict):
                    __slots__ = {

                    }
                outputs = {
                    **args.inputs,
                    "desired_count": args.inputs["desiredCount"],
                    "task_definition_args": args.inputs["taskDefinitionArgs"],
                    "task_definition": TaskDefinitionMock(),
                    "propagate_tags": args.inputs.get("propagateTags"),
                    "enable_execute_command": args.inputs.get("enableExecuteCommand"),
                    "health_check_grace_period_seconds": args.inputs.get("healthCheckGracePeriodSeconds"),
                    "deployment_maximum_percent": args.inputs.get("deploymentMaximumPercent"),
                }
            if args.typ == "aws:rds/cluster:Cluster":
                outputs = {
                    **args.inputs,
                    "endpoint": f"{faker.domain_name()}.cluster-{faker.word()}.us-west-2.rds.amazonaws.com",
                    "vpc_security_group_ids": [faker.word()]
                }
            if args.typ == "random:index/randomPassword:RandomPassword":
                length = args.inputs["length"]
                outputs = {
                    **args.inputs,
                    "result": self.fake_password or faker.password(length=length),
                    "special": args.inputs["special"],
                }
            if args.typ == "cloudflare:index/record:Record":
                outputs = {
                    **args.inputs,
                    "hostname": faker.domain_name()
                }
            if args.typ == "aws:acm/certificate:Certificate":
                outputs = {
                    **args.inputs,
                    "arn": f"arn:aws:acm:us-west-2:123456789012:certificate/{faker.word()}",
                }
            if args.typ == "aws:lb/targetGroup:TargetGroup":
                outputs = {
                    **args.inputs,
                    "arn": f"arn:aws:elasticloadbalancing:us-west-2:123456789012:targetgroup/{faker.word()}",
                }
            if args.typ == "aws:elasticache/cluster:Cluster":
                outputs = {
                    **args.inputs,
                    "cacheNodes": [
                        {
                            "address": f"{faker.domain_name()}.cache.amazonaws.com",
                            "port": 6379,
                        }
                    ],
                }
            if args.typ == "aws:elasticache/parameterGroup:ParameterGroup":
                outputs = {
                    **args.inputs
                }
            if args.typ == "aws:elasticache/parameterGroup:ParameterGroupParameterArgs":
                outputs = {
                    **args.inputs
                }
            if args.typ == "aws:dynamodb/table:Table":
                outputs = {
                    **args.inputs,
                    "arn": f"arn:aws:dynamodb:us-west-2:123456789012:table/{faker.word()}"
                }
            if args.typ == "aws:secretsmanager/secret:Secret":
                outputs = {
                    **args.inputs,
                    "arn": f"arn:aws:secretsmanager:us-west-2:123456789012:secret/{faker.word()}",
                }
            if args.typ == "aws:appautoscaling/policy:Policy":
                outputs = {
                    **args.inputs,
                    "arn": f"arn:aws:appautoscaling:us-west-2:123456789012:policy/{faker.word()}",
                }
            if args.typ == "aws:secretsmanager/secretVersion:SecretVersion":
                outputs = {
                    **args.inputs,
                    "arn": f"arn:aws:secretsmanager:us-west-2:123456789012:secret/{faker.word()}",
                    "secret_string": args.inputs["secretString"],
                }

            if args.typ == "aws:iam/role:Role":
                outputs = {
                    **args.inputs,
                    "arn": f"arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy",
                }
            if args.typ == "awsx:ec2:Vpc":
                outputs = {
                    **args.inputs,
                    "vpc_id": f"vpc-{faker.word()}",
                }
            if args.typ == "aws:ec2/natGateway:NatGateway":
                outputs = {
                    **args.inputs,
                    "nat_gateways": { "asdf": "asdf"}
                }

            if args.typ == "aws:lb/loadBalancer:LoadBalancer":
                outputs = {
                    **args.inputs,
                    "arn": f"arn:aws:elasticloadbalancing:us-west-2:123456789012:loadbalancer/{faker.word()}",
                    "name": f"loadbalancer-{faker.word()}",
                }

            return [args.name + '_id', outputs]

        def call(self, args: pulumi.runtime.MockCallArgs):
            if args.token == "aws:index/getRegion:getRegion":
                return {"name": "us-west-2"}

            if args.token == "aws:secretsmanager/getSecretVersion:getSecretVersion":
                return {
                    "arn": f"arn:aws:secretsmanager:us-west-2:123456789013:secret/my-secrets",
                    "secretString": secret_string
                }

            if args.token == "aws:ec2/getSubnets:getSubnets":
                return {"ids": ["subnet-12345", "subnet-67890"]}
            
            if args.token == "aws:ec2/getVpc:getVpc":
                return {"id": "vpc-12345"}
            
            if args.token == "aws:ec2/getSecurityGroup:getSecurityGroup":
                return {"id": "sg-12345"}

            if args.token == "aws:index/getCallerIdentity:getCallerIdentity":
                return {
                    "account_id": "123456789012",
                    "arn": "arn:aws:sts::123456789012:assumed-role/pulumi/pulumi",
                    "user_id": "AIDAJDPLRKLG7UEXAMPLE",
                }

            raise NotImplementedError(
                "No mock for: " + args.token + " - change PulimiMocks.call"
            )

    return PulumiMocks()


class ImmediateExecutor(ThreadPoolExecutor):
    """This removes multithreading from current tests. Unfortunately in
    presence of multithreading the tests are flaky. The proper fix is
    postponed - see https://github.com/pulumi/pulumi/issues/7663
    """

    def __init__(self):
        super()
        self._default_executor = ThreadPoolExecutor()

    def submit(self, fn, *args, **kwargs):
        v = fn(*args, **kwargs)
        return self._default_executor.submit(ImmediateExecutor._identity, v)

    def map(self, func, *iterables, timeout=None, chunksize=1):
        raise Exception('map not implemented')

    def shutdown(self, wait=True, cancel_futures=False):
        raise Exception('shutdown not implemented')

    @staticmethod
    def _identity(x):
        return x
