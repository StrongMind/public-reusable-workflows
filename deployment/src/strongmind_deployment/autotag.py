# thanks to joeduffy: https://github.com/joeduffy/aws-tags-example/tree/master/autotag-py

import os
import re
from strongmind_deployment.taggable import is_taggable
import pulumi
import subprocess

from strongmind_deployment.operations import get_code_owner_team_name

# tenant values are lowercase kebab-case names from the deploy/kargo/ registry
# in strongmind-platform; anything else poisons cost attribution stack-wide
TENANT_RE = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")


def validate_tenant(tenant):
    if tenant and not TENANT_RE.fullmatch(tenant):
        raise ValueError(
            f"tags:tenant {tenant!r} is not lowercase kebab-case; it must be a "
            "tenant name from the deploy/kargo/ registry in strongmind-platform"
        )
    return tenant


########################
###### Entrypoint ######

class StandardTags:
    """
    Represents the default tags that will be assigned to all projects.
    Dependencies are: 
     * Pulumi Config files for service and product.
     * Pulumi Project / Stack for project and environment.
     * Git for the repository name.
     * CODEOWNERS file for owner.
    """
    def __init__(
        self,
        extra_tags: dict,
        project: str = None,
        environment: str = None,
        service: str = None,
        product: str = None,
        repository: str = None,
        tenant: str = None,
        app: str = None,
    ):
        config = pulumi.Config("tags")
        self.extra_tags = extra_tags
        self.project = project or pulumi.get_project()
        self.environment = environment or pulumi.get_stack()
        self.service = service or config.require("service")
        self.product = product or config.require("product")
        # get the git repository from the current git repo if not provided
        self.repository = repository or config.get("repository") or get_repo_name()
        self.owner = get_code_owner_team_name()
        # tenant is optional until every repo has set tags:tenant; a set value
        # must be shaped like a registry name (full registry check is the CI
        # gate's job, not this library's).
        self.tenant = validate_tenant(tenant or config.get("tenant"))
        # app must equal the Datadog service value (ADR-0004), which is the
        # service tag by the DEVOPS-16364 decision. app_explicit records
        # whether a caller chose the value, or it merely defaulted from
        # service — a defaulted app must follow service wherever service is
        # overridden later (parity), an explicit one must not.
        self.app_explicit = bool(app or config.get("app"))
        self.app = app or config.get("app") or self.service


def get_standard_tags(extra_tags:dict):
    """
    Use this entrypoint if you need the tags, and auto-tagging isn't working for you.
    This is useful for resources that need a different tagging format, like AutoScalingGroups
    merges the dictionary of tags and sets standard tags here
    """
    standard_tags = StandardTags(extra_tags)
    merged = {
        "environment": standard_tags.environment,
        "project": standard_tags.project,
        "service": standard_tags.service,
        "product": standard_tags.product,
        "repository": standard_tags.repository,
        "owner": standard_tags.owner,
        "app": standard_tags.app,
        # a missing tenant stays missing rather than guessing: backfill and
        # cost attribution must never see an unreviewed value
        **({"tenant": standard_tags.tenant} if standard_tags.tenant else {}),
        **extra_tags,
    }
    # a defaulted app follows the FINAL service value, so an extra_tags
    # service override cannot break app == service parity
    if not standard_tags.app_explicit and "app" not in extra_tags:
        merged["app"] = merged["service"]
    return merged


def add_standard_billing_tags(extra_tags:dict):
    """
    Main Entrypoint
    Adds tagging to all resources in the stack.

    Example:
    ```python
        from strongmind_deployment import vpc, autotag

        extra_tags = {
            "map-migrated": "migP6SOEO44BT",
        }

        all_tags = autotag.get_standard_tags(extra_tags)
        autotag.add_standard_billing_tags(all_tags)
    ```
    """
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in extra_tags.items()):
        raise ValueError("All keys and values in 'extra_tags' must be strings.")

    standard_tags = StandardTags(extra_tags)
    app_explicit = standard_tags.app_explicit or "app" in extra_tags
    register_auto_tags(get_standard_tags(extra_tags), app_explicit=app_explicit)


def component_tags(project: str, env_name: str, owning_team: str) -> dict:
    """
    The tag dict the deployment components (RailsComponent children et al.)
    stamp on their resources — the single source for that set, so tenant/app
    cannot be adopted in one place and missed in another.
    app mirrors service (app == service parity, DEVOPS-16345); tenant comes
    from tags:tenant Pulumi config and is omitted, never guessed, when unset.
    """
    tags = {
        "product": project,
        "repository": project,
        "service": project,
        "environment": env_name,
        "owner": owning_team,
        "app": project,
    }
    tenant = validate_tenant(pulumi.Config("tags").get("tenant"))
    if tenant:
        tags["tenant"] = tenant
    return tags


#### End Entrypoint ####
########################


##############################
##### Internal Functions #####


def get_repo_name():
    """
    Get the repository name from the current git repository.
    """
    try:
        result = subprocess.run(
            ["basename $(git rev-parse --show-toplevel)"],
            capture_output=True,
            text=True,
            shell=True,
        )
        return f"{result.stdout.strip()}"
    except Exception as e:
        print(
            f"ERROR fetching git repository. Please set this in 'add_standard_billing_tags': {e}"
        )
        return "notset"


# registerAutoTags registers a global stack transformation that merges a set
# of tags with whatever was also explicitly added to the resource definition.
def register_auto_tags(auto_tags: dict, app_explicit: bool = False):
    pulumi.log.info(f"Resources will be tagged with: {auto_tags}")
    pulumi.runtime.register_stack_transformation(lambda args: auto_tag(args, auto_tags, app_explicit))


def auto_tag(args, auto_tags, app_explicit: bool = False):
    if is_taggable(args.type_):
        # Ensure that the "tags" property is set in args.props
        existing_tags = args.props.get("tags", {}) or {}

        # Check if auto_tags is not None and is a dictionary before processing
        if auto_tags and isinstance(auto_tags, dict):
            # Check if any of the auto_tags already exist in the resource's tags
            new_tags = {k: v for k, v in auto_tags.items() if k not in existing_tags}

            # a resource carrying its own service tag (component children)
            # keeps app == ITS service, unless a caller chose app explicitly
            if not app_explicit and "app" not in existing_tags and "service" in existing_tags:
                new_tags["app"] = existing_tags["service"]

            args.props["tags"] = {**(existing_tags), **new_tags}

        return pulumi.ResourceTransformationResult(args.props, args.opts)
    # If resources aren't in the taggable list they will be skipped. 
    # If you want to know if there are resources that are not being tagged, 
    # you can enable this environment variable and you will see a list of resources that this process isn't tagging.
    else:
       if os.getenv("DEBUG_LOG_UNTAGGED_RESOURCES", False):
            print(f"Skipping auto-tagging for {args.type_}")
