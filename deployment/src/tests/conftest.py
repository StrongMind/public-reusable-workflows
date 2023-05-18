import asyncio
from concurrent.futures import ThreadPoolExecutor

import pulumi
import pytest

from tests.mocks import ImmediateExecutor


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