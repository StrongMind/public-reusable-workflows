import pulumi.runtime
import pulumi_aws.s3
import pytest

from tests.mocks import get_pulumi_mocks
from tests.shared import assert_output_equals, assert_outputs_equal