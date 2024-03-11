from pulumi import Output
from pulumi_aws import lb
from strongmind_deployment.util import get_project_stack, get_project_stack_name


class AlbTargetArgs:
    def __init__(
        self,
        vpc_id: Output[str],
        port: int = 80,
        health_check_path: str = "/up",
        health_check_interval: int = 30,
        health_check_timeout: int = 5,
        healthy_threshold: int = 5,
        unhealthy_threshold: int = 2,
    ):
        self.port = port
        self.vpc_id = vpc_id
        self.health_check_path = health_check_path
        self.health_check_interval = health_check_interval
        self.health_check_timeout = health_check_timeout
        self.healthy_threshold = healthy_threshold
        self.unhealthy_threshold = unhealthy_threshold


class AlbTarget:
    """
    Currently only supports IP targets.
    """
    def __init__(self, name: str, args: AlbTargetArgs, opts: None):
        super().__init__('strongmind:global_build:commons:alb_target', name, None, opts)
        self.name = name
        self.project_stack = get_project_stack()
        self.args = args

        self.create_resources()

    def create_resources(self):
        self.create_target_group()

    def create_target_group(self) -> lb.TargetGroup:
        resource_name = f"{get_project_stack_name('ecs-target')}"

        return lb.TargetGroup(
            resource_name,
            name=self.project_stack,
            port=self.args.port,
            protocol="HTTP",
            target_type="ip",
            vpc_id=self.args.vpc_id,
            health_check=lb.TargetGroupHealthCheckArgs(
                enabled=True,
                path=self.args.health_check_path,
                port=str(self.args.port),
                protocol="HTTP",
                matcher="200",
                interval=self.args.health_check_interval,
                timeout=self.args.health_check_timeout,
                healthy_threshold=self.args.healthy_threshold,
                unhealthy_threshold=self.args.unhealthy_threshold,
            ),
        )
