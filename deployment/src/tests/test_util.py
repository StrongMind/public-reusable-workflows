import pytest
from strongmind_deployment.util import qualify_component_name

def describe_qualify_component_name():
    def test_qualify_component_name_truncate():
        result = qualify_component_name("enterprise-stage1-enterprise-stage1-component", {"namespace": "test"}, True)
        assert result == "test-enterprise-stage1-enterpris"

    def test_qualify_component_name_with_namespace():
        result = qualify_component_name("component", {"namespace": "test"})
        assert result == "test-component"

    def test_qualify_component_name_without_namespace():
        result = qualify_component_name("component", {})
        assert result == "component"