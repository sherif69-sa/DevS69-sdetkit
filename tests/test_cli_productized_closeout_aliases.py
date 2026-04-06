from __future__ import annotations

import pytest

from sdetkit import cli


@pytest.mark.parametrize(
    ("canonical", "legacy", "module_attr"),
    [
        ("expansion-automation", "expansion-automation", "expansion_automation_41"),
        (
            "optimization-closeout-foundation",
            "optimization-closeout-foundation",
            "optimization_closeout_42",
        ),
        ("acceleration-closeout", "acceleration-closeout", "acceleration_closeout_43"),
        ("scale-closeout", "scale-closeout", "scale_closeout_44"),
        ("expansion-closeout", "expansion-closeout", "expansion_closeout_45"),
        ("optimization-closeout", "optimization-closeout", "optimization_closeout_46"),
        ("reliability-closeout", "reliability-closeout", "reliability_closeout_47"),
        ("objection-closeout", "objection-closeout", "objection_closeout_48"),
        ("weekly-review-closeout", "weekly-review-closeout", "weekly_review_closeout_49"),
        (
            "execution-prioritization-closeout",
            "execution-prioritization-closeout",
            "execution_prioritization_closeout_50",
        ),
    ],
)
def test_canonical_and_legacy_commands_dispatch(
    monkeypatch, canonical: str, legacy: str, module_attr: str
) -> None:
    calls: list[list[str]] = []

    def _fake_main(argv: list[str]) -> int:
        calls.append(list(argv))
        return 0

    monkeypatch.setattr(getattr(cli, module_attr), "main", _fake_main)

    assert cli.main([canonical, "--format", "json"]) == 0
    assert cli.main([legacy, "--format", "json"]) == 0
    assert calls == [["--format", "json"], ["--format", "json"]]
