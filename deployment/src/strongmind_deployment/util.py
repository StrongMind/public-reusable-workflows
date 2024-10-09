import pulumi
import pulumi_aws as aws

def get_project_stack() -> str:
    """
    Typically used in pulumi logical and physical resource naming
    """
    stack = pulumi.get_stack()
    project = pulumi.get_project()
    return f"{project}-{stack}"

def get_stack_project() -> str:
    """
    Typically used in DNS naming.
    """
    stack = pulumi.get_stack()
    project = pulumi.get_project()
    return f"{stack}-{project}"

def get_account_stack_name(force_stack: str = None) -> str:
    """
    Typically used to retrieve a Pulumi stack reference for the current account stack.
    """
    alias = aws.iam.get_account_alias().account_alias
    account_stack_name = alias.replace("-","_")
    account_stack = force_stack or account_stack_name
    return f"organization/account/{account_stack}"


def create_ecs_cluster(parent_component, name):
    return aws.ecs.Cluster("cluster",
                           name=name,
                           tags=parent_component.tags,
                           settings=[{
                               "name": "containerInsights",
                               "value": "enabled",
                           }],
                           opts=pulumi.ResourceOptions(parent=parent_component),
                           )
