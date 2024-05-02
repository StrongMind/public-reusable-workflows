#!/bin/python3
import sys
sys.path.append("..")

import pulumi
import pulumi_aws as aws
import json

from storage import StorageComponent

from batch import BatchComponent

stack_name = pulumi.get_stack()

batch = BatchComponent(
    name="batch",
    command=["echo", "hello world"],
    #max_vcpus=256,
    priority=1,
)
