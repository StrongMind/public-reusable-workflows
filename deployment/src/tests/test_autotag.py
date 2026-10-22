from unittest import mock

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

    def test_explicit_params_win():
        tags_dict = standard_tags(tenant="course-pro", app="cartman-worker")
        assert tags_dict["tenant"] == "course-pro"
        assert tags_dict["app"] == "cartman-worker"

    def test_existing_standard_tags_unchanged():
        tags = standard_tags(config_values={"tenant": "course-pro"})
        assert tags["service"] == "cartman"
        assert tags["product"] == "cartman"
        assert tags["owner"] == "skunkworks"
        assert tags["repository"] == "cartman"
