from __future__ import annotations

from sdetkit import cli


def test_adoption_command_forwards_to_adoption_module(monkeypatch) -> None:
    captured: list[tuple[str, list[str]]] = []

    def _fake_run(module_name: str, args: list[str]) -> int:
        captured.append((module_name, list(args)))
        return 0

    monkeypatch.setattr(cli, "_run_module_main", _fake_run)

    rc = cli.main(
        [
            "adoption",
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
        ]
    )
    assert rc == 0
    assert captured == [
        (
            "sdetkit.adoption",
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
                "--policy-profile",
                "balanced",
            ],
        )
    ]


def test_adoption_command_forwards_custom_policy_and_thresholds(monkeypatch) -> None:
    captured: list[tuple[str, list[str]]] = []

    def _fake_run(module_name: str, args: list[str]) -> int:
        captured.append((module_name, list(args)))
        return 0

    monkeypatch.setattr(cli, "_run_module_main", _fake_run)
    rc = cli.main(
        [
            "adoption",
            "--fit",
            "fit.json",
            "--summary",
            "summary.json",
            "--policy-profile",
            "conservative",
            "--escalation-consecutive-no-ship",
            "6",
        ]
    )
    assert rc == 0
    assert captured == [
        (
            "sdetkit.adoption",
            [
                "--fit",
                "fit.json",
                "--summary",
                "summary.json",
                "--format",
                "json",
                "--policy-profile",
                "conservative",
                "--escalation-consecutive-no-ship",
                "6",
            ],
        )
    ]
