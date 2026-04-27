from __future__ import annotations

from sdetkit import cli


def test_start_command_forwards_to_onboarding(monkeypatch) -> None:
    captured: list[tuple[str, list[str]]] = []

    def _fake_run(module_name: str, args: list[str]) -> int:
        captured.append((module_name, list(args)))
        return 0

    monkeypatch.setattr(cli, "_run_module_main", _fake_run)

    rc = cli.main(
        [
            "start",
            "--role",
            "sdet",
            "--journey",
            "fast-start",
            "--platform",
            "linux",
            "--format",
            "markdown",
        ]
    )
    assert rc == 0
    assert captured == [
        (
            "sdetkit.onboarding",
            [
                "--role",
                "sdet",
                "--journey",
                "fast-start",
                "--platform",
                "linux",
                "--format",
                "markdown",
            ],
        )
    ]
