import pulumi

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
  stack = pulumi.get_stack()
  stack_part = "prod" if "prod" in stack else "stage"
  account_stack = force_stack or f"strongmind_{stack_part}"
  return f"organization/account/{account_stack}"