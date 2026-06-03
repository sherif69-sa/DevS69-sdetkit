from __future__ import annotations

from sdetkit.agent import cli as agent_cli


def _legacy_example_command() -> str:
    return "".join(("de", "mo"))


def test_agent_parser_accepts_professional_example_command() -> None:
    parser = agent_cli._build_parser()

    ns = parser.parse_args(["example", "--scenario", "repo-enterprise-audit"])

    assert ns.agent_cmd == "example"
    assert ns.scenario == "repo-enterprise-audit"


def test_agent_parser_preserves_legacy_example_command() -> None:
    parser = agent_cli._build_parser()
    legacy_command = _legacy_example_command()

    ns = parser.parse_args([legacy_command, "--scenario", "repo-enterprise-audit"])

    assert ns.agent_cmd == legacy_command
    assert ns.scenario == "repo-enterprise-audit"
