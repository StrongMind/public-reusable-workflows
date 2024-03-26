# thanks to joeduffy: https://github.com/joeduffy/aws-tags-example/tree/master/autotag-py

from typing import Dict
from strongmind_deployment.taggable import is_taggable
import pulumi
import subprocess

#
# 
########################
###### Entrypoint ######

class StandardTags:
    def __init__(
        self,
        extra_tags: dict,
        project: str = None,
        environment: str = None,
        service: str = None,
        product: str = None,
        repository: str = None,
    ):
        config = pulumi.Config("tags")
        self.extra_tags = extra_tags
        self.project = project or pulumi.get_project()
        self.environment = environment or pulumi.get_stack()
        self.service = service or config.require("service")
        self.product = product or config.require("product")
        # get the git repository from the current git repo if not provided
        self.repository = repository or config.get("repository") or get_repo_name()


def get_standard_tags(extra_tags:dict):
    """
    Use this entrypoint if you need the tags, and auto-tagging isn't working for you.
    This is useful for resources that need a different tagging format, like AutoScalingGroups
    merges the dictionary of tags and sets standard tags here
    """
    standard_tags = StandardTags(extra_tags)
    return {
        "environment": pulumi.get_stack(),
        "project": pulumi.get_project(),
        "environment": standard_tags.environment,
        "project": standard_tags.project,
        "service": standard_tags.service,
        "product": standard_tags.product,
        "repository": standard_tags.repository,
        **extra_tags,
    }


def add_standard_billing_tags(extra_tags:dict):
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in extra_tags.items()):
    Main Entrypoint
    if not all(
        raise ValueError("All keys and values in 'extra_tags' must be strings.")
    
    register_auto_tags(get_standard_tags(extra_tags))

#### End Entrypoint ####
########################


##############################
##### Internal Functions #####

# registerAutoTags registers a global stack transformation that merges a set
# of tags with whatever was also explicitly added to the resource definition.
def register_auto_tags(auto_tags: dict):
    pulumi.log.info(f"Resources will be tagged with: {auto_tags}")
    pulumi.runtime.register_stack_transformation(lambda args: auto_tag(args, auto_tags))


def auto_tag(args, auto_tags):
    if is_taggable(args.type_):
        # Ensure that the "tags" property is set in args.props
        existing_tags = args.props.get("tags", {}) or {}

        # Check if auto_tags is not None and is a dictionary before processing
        if auto_tags and isinstance(auto_tags, dict):
            # Check if any of the auto_tags already exist in the resource's tags
            new_tags = {k: v for k, v in auto_tags.items() if k not in existing_tags}

            args.props["tags"] = {**(existing_tags), **new_tags}

        return pulumi.ResourceTransformationResult(args.props, args.opts)


# # auto_tag applies the given tags to the resource properties if applicable.
# def auto_tag(args, auto_tags):
#     if is_taggable(args.type_):
#         # Ensure that the "tags" property is set in args.props
#         existing_tags = args.props.get("tags", {}) or {}

#         # Check if auto_tags is not None and is a dictionary before processing
#         if auto_tags and isinstance(auto_tags, dict):
#             print(f"Auto-tagging {args.type_}")
#             # Check if any of the auto_tags already exist in the resource's tags
#             new_tags = {k: v for k, v in auto_tags.items() if k not in existing_tags}
#             args.props["tags"] = {**(existing_tags), **new_tags}

#             return pulumi.ResourceTransformationResult(args.props, args.opts)
    # else:
    # # uncomment to print resources if you think we need to add more to taggable.py.
    #     print(f"Skipping auto-tagging for {args.type_}")
