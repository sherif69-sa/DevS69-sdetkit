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
            ],
        )
    ]
