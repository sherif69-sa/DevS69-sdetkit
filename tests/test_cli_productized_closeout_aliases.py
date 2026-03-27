from __future__ import annotations

import pytest

from sdetkit import cli


@pytest.mark.parametrize(
    ("canonical", "legacy", "module_attr"),
    [
        ("expansion-automation", "expansion-automation", "day41_expansion_automation"),
        (
            "optimization-closeout-foundation",
            "optimization-closeout-foundation",
            "day42_optimization_closeout",
        ),
        ("acceleration-closeout", "acceleration-closeout", "day43_acceleration_closeout"),
        ("scale-closeout", "scale-closeout", "day44_scale_closeout"),
        ("expansion-closeout", "expansion-closeout", "day45_expansion_closeout"),
        ("optimization-closeout", "optimization-closeout", "day46_optimization_closeout"),
        ("reliability-closeout", "day47-reliability-closeout", "day47_reliability_closeout"),
        ("objection-closeout", "objection-closeout", "day48_objection_closeout"),
        ("weekly-review-closeout", "weekly-review-closeout", "day49_weekly_review_closeout"),
        (
            "execution-prioritization-closeout",
            "day50-execution-prioritization-closeout",
            "day50_execution_prioritization_closeout",
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
