import pytest

from strongmind_deployment.operations import service_owner_team


def describe_service_owner_team():
    def it_reads_the_team_on_the_catch_all_line():
        assert service_owner_team("* @StrongMind/steakholders\n") == "steakholders"

    def it_ignores_path_specific_reviewers():
        codeowners = (
            "/.github/* @StrongMind/binary-ops\n"
            "/infrastructure/* @StrongMind/binary-ops\n"
            "* @StrongMind/qwerty-talkers\n"
            "/db/migrate/* @StrongMind/qwerty-talkers @StrongMind/experiment-626\n"
        )
        assert service_owner_team(codeowners) == "qwerty-talkers"

    def it_ignores_people_on_the_catch_all_line():
        assert service_owner_team("* @JoshuaGleason @StrongMind/devops\n") == "devops"

    def it_uses_the_last_catch_all_line_like_github():
        assert service_owner_team("* @StrongMind/next-level\n* @StrongMind/team-ai\n") == "team-ai"

    def it_lower_cases_the_team():
        assert service_owner_team("* @StrongMind/XXX\n") == "xxx"

    @pytest.mark.parametrize("codeowners", [
        "/.github/* @StrongMind/binary-ops\n",
        "* @Toacin @Jbrito6492\n",
        "* @StrongMind/skunkworks @StrongMind/xxx\n",
        "# * @StrongMind/xxx\n",
        "",
    ])
    def it_rejects_a_catch_all_line_without_exactly_one_team(codeowners):
        with pytest.raises(ValueError, match="one team on its `\\*` line"):
            service_owner_team(codeowners)
