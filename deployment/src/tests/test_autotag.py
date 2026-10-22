from unittest import mock

import pytest

from strongmind_deployment import autotag


def standard_tags(tenant=None, app=None, config_values=None):
    config_values = config_values or {}
    with mock.patch.object(autotag, "pulumi") as pulumi_mock, \
         mock.patch.object(autotag, "get_code_owner_team_name", return_value="skunkworks"):
        pulumi_mock.get_project.return_value = "proj"
        pulumi_mock.get_stack.return_value = "prod"
        config = pulumi_mock.Config.return_value
        config.require.side_effect = lambda k: {"service": "cartman", "product": "cartman"}[k]
        config.get.side_effect = lambda k: config_values.get(k)
        st = autotag.StandardTags({}, tenant=tenant, app=app, repository="cartman")
        with mock.patch.object(autotag, "StandardTags", return_value=st):
            return autotag.get_standard_tags({})


def describe_tenant_and_app_tags():
    def test_app_defaults_to_the_service_value():
        tags = standard_tags()
        assert tags["app"] == "cartman"

    def test_app_config_overrides_service():
        tags = standard_tags(config_values={"app": "cartman-api"})
        assert tags["app"] == "cartman-api"

    def test_tenant_comes_from_config():
        tags = standard_tags(config_values={"tenant": "course-pro"})
        assert tags["tenant"] == "course-pro"

    def test_missing_tenant_is_omitted_not_guessed():
        tags = standard_tags()
        assert "tenant" not in tags

    def test_explicit_params_win_over_config():
        with mock.patch.object(autotag, "pulumi") as p, \
             mock.patch.object(autotag, "get_code_owner_team_name", return_value="skunkworks"):
            c = p.Config.return_value
            c.require.side_effect = lambda k: {"service": "cartman", "product": "cartman"}[k]
            c.get.side_effect = {"tenant": "identity", "app": "cartman-api",
                                 "repository": "cartman"}.get
            st = autotag.StandardTags({}, tenant="course-pro", app="cartman-worker")
        assert (st.tenant, st.app) == ("course-pro", "cartman-worker")

    def test_extra_tags_override_app_and_tenant():
        with mock.patch.object(autotag, "pulumi") as p, \
             mock.patch.object(autotag, "get_code_owner_team_name", return_value="skunkworks"):
            c = p.Config.return_value
            c.require.side_effect = lambda k: {"service": "cartman", "product": "cartman"}[k]
            c.get.side_effect = {"tenant": "course-pro", "repository": "cartman"}.get
            tags = autotag.get_standard_tags({"app": "override-app", "tenant": "kong"})
        assert tags["app"] == "override-app"
        assert tags["tenant"] == "kong"

    def test_defaulted_app_follows_service_override():
        with mock.patch.object(autotag, "pulumi") as p, \
             mock.patch.object(autotag, "get_code_owner_team_name", return_value="skunkworks"):
            c = p.Config.return_value
            c.require.side_effect = lambda k: {"service": "cartman", "product": "cartman"}[k]
            c.get.side_effect = {"repository": "cartman"}.get
            tags = autotag.get_standard_tags({"service": "cartman-worker"})
        assert tags["service"] == "cartman-worker"
        assert tags["app"] == "cartman-worker"

    def test_invalid_tenant_raises():
        with mock.patch.object(autotag, "pulumi") as p, \
             mock.patch.object(autotag, "get_code_owner_team_name", return_value="skunkworks"):
            c = p.Config.return_value
            c.require.side_effect = lambda k: {"service": "cartman", "product": "cartman"}[k]
            c.get.side_effect = {"repository": "cartman"}.get
            for bad in ("CoursePro", "course_pro", "course pro", "-course-pro"):
                with pytest.raises(ValueError):
                    autotag.StandardTags({}, tenant=bad)

    def test_existing_standard_tags_unchanged():
        tags = standard_tags(config_values={"tenant": "course-pro"})
        assert tags["service"] == "cartman"
        assert tags["product"] == "cartman"
        assert tags["owner"] == "skunkworks"
        assert tags["repository"] == "cartman"


class FakeArgs:
    def __init__(self, type_, props):
        self.type_ = type_
        self.props = props
        self.opts = None


def describe_auto_tag_transformation():
    def _transform(props, auto_tags, app_explicit=False):
        with mock.patch.object(autotag, "is_taggable", return_value=True), \
             mock.patch.object(autotag.pulumi, "ResourceTransformationResult",
                               side_effect=lambda props, opts: (props, opts)):
            result_props, _ = autotag.auto_tag(FakeArgs("aws:s3/bucket:Bucket", props), auto_tags, app_explicit)
        return result_props["tags"]

    def test_never_overwrites_resource_own_tags():
        tags = _transform({"tags": {"service": "secrets-child", "owner": "keep"}},
                         {"service": "cartman", "owner": "skunkworks", "tenant": "course-pro", "app": "cartman"})
        assert tags["service"] == "secrets-child"
        assert tags["owner"] == "keep"
        assert tags["tenant"] == "course-pro"

    def test_component_child_keeps_app_service_parity():
        # resource carries its own service (component dict); defaulted app follows it
        tags = _transform({"tags": {"service": "attendance-approver"}},
                         {"service": "bulk-attendance-approver", "app": "bulk-attendance-approver"})
        assert tags["app"] == "attendance-approver"

    def test_explicit_app_is_respected_on_component_children():
        tags = _transform({"tags": {"service": "attendance-approver"}},
                         {"service": "bulk-attendance-approver", "app": "chosen-app"},
                         app_explicit=True)
        assert tags["app"] == "chosen-app"


def describe_component_tags():
    def _component(config_values=None):
        with mock.patch.object(autotag, "pulumi") as p:
            p.Config.return_value.get.side_effect = (config_values or {}).get
            return autotag.component_tags("cartman", "prod", "skunkworks")

    def test_app_mirrors_service():
        tags = _component()
        assert tags["service"] == tags["app"] == "cartman"
        assert tags["owner"] == "skunkworks"
        assert tags["environment"] == "prod"

    def test_tenant_from_config_when_set():
        assert _component({"tenant": "course-pro"})["tenant"] == "course-pro"

    def test_tenant_omitted_when_unset():
        assert "tenant" not in _component()

    def test_invalid_tenant_raises():
        with pytest.raises(ValueError):
            _component({"tenant": "Course_Pro"})
