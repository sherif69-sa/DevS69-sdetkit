from __future__ import annotations

from sdetkit import cli


def test_fit_command_forwards_to_fit_module(monkeypatch) -> None:
    captured: list[tuple[str, list[str]]] = []

    def _fake_run(module_name: str, args: list[str]) -> int:
        captured.append((module_name, list(args)))
        return 0

    monkeypatch.setattr(cli, "_run_module_main", _fake_run)
    rc = cli.main(
        [
            "fit",
            "--repo-size",
            "medium",
            "--team-size",
            "medium",
            "--release-frequency",
            "high",
            "--change-failure-impact",
            "high",
            "--compliance-pressure",
            "medium",
            "--format",
            "json",
            "--out",
            "fit.json",
        ]
    )
    assert rc == 0
    assert captured == [
        (
            "sdetkit.fit",
            [
                "--repo-size",
                "medium",
                "--team-size",
                "medium",
                "--release-frequency",
                "high",
                "--change-failure-impact",
                "high",
                "--compliance-pressure",
                "medium",
                "--format",
                "json",
                "--out",
                "fit.json",
            ],
        )
    ]
