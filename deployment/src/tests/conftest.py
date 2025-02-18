import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from random import randint

import pulumi
import pytest
import boto3
from moto import mock_ecs

from tests.mocks import ImmediateExecutor

@pytest.fixture(scope="session", autouse=True)
def faker_seed():
    return randint(0, 100000)

@pytest.fixture
def pulumi_set_mocks(pulumi_mocks, app_name, stack):
    loop = asyncio.get_event_loop()
    loop.set_default_executor(ImmediateExecutor())
    old_settings = pulumi.runtime.settings.SETTINGS
    try:
        pulumi.runtime.mocks.set_mocks(
            pulumi_mocks,
            project=app_name,
            stack=stack,
            preview=False)
        yield True
    finally:
        pulumi.runtime.settings.configure(old_settings)
        loop.set_default_executor(ThreadPoolExecutor())


@pytest.fixture(autouse=True)
def aws_credentials():
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = 'us-east-1'

    yield os.environ

@pytest.fixture(autouse=True)
def mock_boto():
    with mock_ecs():
        ecs = boto3.client('ecs', region_name='us-west-2')
        
        # Create a test cluster
        ecs.create_cluster(
            clusterName='test-cluster'
        )
        
        # Create a test service
        ecs.create_service(
            cluster='test-cluster',
            serviceName='test-service',
            taskDefinition='test-task:1',
            desiredCount=2,
            deploymentConfiguration={
                'maximumPercent': 200,
                'minimumHealthyPercent': 50
            }
        )
        
        yield ecs
