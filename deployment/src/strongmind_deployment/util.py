import pulumi
import pulumi_aws as aws

def get_project_stack_name(name: str) -> str:
    """
    Use this to consistently name resources.
    """
    return f"{get_project_stack()}-{name}"

def get_project_stack() -> str:
  stack = pulumi.get_stack()
  project = pulumi.get_project()
  return f"{project}-{stack}"

def get_account_stack_name(force_stack: str = None) -> str:
    alias = aws.iam.get_account_alias().account_alias
    account_stack_name = alias.replace("-","_")
    account_stack = force_stack or account_stack_name
    return f"organization/account/{account_stack}"
