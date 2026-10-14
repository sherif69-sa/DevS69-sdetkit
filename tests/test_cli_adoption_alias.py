from __future__ import annotations

import pytest

from sdetkit import cli


@pytest.mark.parametrize(
    "args",
    [
        [
            "--fit",
            "fit.json",
            "--summary",
            "summary.json",
            "--format",
            "md",
            "--out",
            "out.md",
            "--history",
            "hist.jsonl",
            "--history-rollup-out",
            "hist-rollup.json",
        ],
        [
            "--fit",
            "fit.json",
            "--summary",
            "summary.json",
            "--policy-profile",
            "conservative",
            "--escalation-consecutive-no-ship",
            "6",
        ],
    ],
)
def test_adoption_command_forwards_arguments_unchanged(monkeypatch, args: list[str]) -> None:
    captured: list[tuple[str, list[str]]] = []

    def _fake_run(module_name: str, forwarded: list[str]) -> int:
        captured.append((module_name, list(forwarded)))
        return 0

    monkeypatch.setattr(cli, "_run_module_main", _fake_run)

    assert cli.main(["adoption", *args]) == 0
    assert captured == [("sdetkit.adoption", args)]
