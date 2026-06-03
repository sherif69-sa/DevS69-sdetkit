from __future__ import annotations

from sdetkit.cli import playbooks_cli


def _cmd(*parts: str) -> str:
    return "-".join(parts)


def _legacy_phase(number: str, suffix: str) -> str:
    return f"phase{number}-{suffix}"


def test_playbooks_registry_promotes_baseline_and_release_readiness_names() -> None:
    cmd_to_mod, _alias_to_canonical = playbooks_cli._build_registry(playbooks_cli._pkg_dir())

    assert _cmd("baseline", "hardening") in cmd_to_mod
    assert _cmd("baseline", "wrap") in cmd_to_mod
    assert _cmd("release", "readiness", "kickoff") in cmd_to_mod


def test_playbooks_registry_keeps_legacy_phase_commands_directly_available() -> None:
    cmd_to_mod, alias_to_canonical = playbooks_cli._build_registry(playbooks_cli._pkg_dir())

    expected_pairs = {
        _legacy_phase("1", "hardening"): _cmd("baseline", "hardening"),
        _legacy_phase("1", "wrap"): _cmd("baseline", "wrap"),
        _legacy_phase("2", "kickoff"): _cmd("release", "readiness", "kickoff"),
    }

    for legacy, canonical in expected_pairs.items():
        assert legacy in cmd_to_mod
        assert canonical in cmd_to_mod
        assert legacy not in alias_to_canonical
        assert cmd_to_mod[legacy] == cmd_to_mod[canonical]


def test_playbooks_listing_exposes_legacy_and_professional_names() -> None:
    payload = playbooks_cli._list_payload(
        want_recommended=False,
        want_legacy=False,
        want_aliases=False,
        search=None,
    )

    legacy = payload["legacy"]
    playbooks = payload["playbooks"]

    assert isinstance(legacy, list)
    assert isinstance(playbooks, list)
    assert _legacy_phase("1", "hardening") in legacy
    assert _legacy_phase("1", "wrap") in legacy
    assert _legacy_phase("2", "kickoff") in legacy
    assert _cmd("baseline", "hardening") in playbooks
    assert _cmd("baseline", "wrap") in playbooks
    assert _cmd("release", "readiness", "kickoff") in playbooks
