from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from sdetkit import cli


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, list[str]]]:
    recorded: list[tuple[str, list[str]]] = []

    def _fake_run(module_name: str, args: list[str]) -> int:
        recorded.append((module_name, list(args)))
        return 7

    monkeypatch.setattr(cli, "_run_module_main", _fake_run)
    return recorded


@pytest.mark.parametrize(
    "name", sorted(set(cli.COMMANDS) - set(cli.SUBCOMMANDS) - {"apiget", "cassette-get"})
)
def test_every_command_dispatches_to_its_module(
    name: str, calls: list[tuple[str, list[str]]]
) -> None:
    command = cli.COMMANDS[name]

    assert cli.main([name, "--flag", "value"]) == 7
    assert calls == [(command.module, [*command.prefix, "--flag", "value"])]


def test_init_and_dev_route_to_repo_subcommands(calls: list[tuple[str, list[str]]]) -> None:
    cli.main(["init", "--dry-run"])
    cli.main(["dev", "precommit"])

    assert calls == [
        ("sdetkit.repo", ["init", "--dry-run"]),
        ("sdetkit.repo", ["dev", "precommit"]),
    ]


@pytest.mark.parametrize(
    ("subcommand", "module"),
    [
        ("gate", "sdetkit.gate"),
        ("doctor", "sdetkit.doctor"),
        ("security", "sdetkit.security_gate"),
        ("evidence", "sdetkit.evidence"),
        ("repo", "sdetkit.repo"),
    ],
)
def test_release_routes_subcommands(
    subcommand: str, module: str, calls: list[tuple[str, list[str]]]
) -> None:
    assert cli.main(["release", subcommand, "fast"]) == 7
    assert calls == [(module, ["fast"])]


@pytest.mark.parametrize("args", [[], ["publish"]])
def test_release_rejects_missing_or_unknown_subcommand(
    args: list[str], calls: list[tuple[str, list[str]]], capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["release", *args]) == 2
    assert calls == []
    assert "release error: expected a subcommand (gate|doctor|security|evidence|repo)" in (
        capsys.readouterr().err
    )


def test_apiget_without_cassette_passes_arguments_through(
    calls: list[tuple[str, list[str]]],
) -> None:
    assert cli.main(["apiget", "https://example.test", "--retries", "2"]) == 7
    assert calls == [("sdetkit.apiget", ["https://example.test", "--retries", "2"])]


@pytest.mark.parametrize(
    ("args", "expected_mode"),
    [
        (["--cassette", "c.json", "--cassette-mode", "replay"], "replay"),
        (["--cassette=c.json", "--cassette-mode=record"], "record"),
        (["--cassette", "c.json"], "auto"),
    ],
)
def test_apiget_cassette_flags_become_environment_for_the_call_only(
    monkeypatch: pytest.MonkeyPatch, args: list[str], expected_mode: str
) -> None:
    monkeypatch.setenv("SDETKIT_CASSETTE_MODE", "previous")
    monkeypatch.delenv("SDETKIT_CASSETTE", raising=False)
    seen: dict[str, object] = {}

    def _fake_run(module_name: str, forwarded: list[str]) -> int:
        seen["module"] = module_name
        seen["args"] = list(forwarded)
        seen["cassette"] = os.environ.get("SDETKIT_CASSETTE")
        seen["mode"] = os.environ.get("SDETKIT_CASSETTE_MODE")
        return 0

    monkeypatch.setattr(cli, "_run_module_main", _fake_run)

    assert cli.main(["apiget", "https://example.test", *args]) == 0
    assert seen == {
        "module": "sdetkit.apiget",
        "args": ["https://example.test"],
        "cassette": "c.json",
        "mode": expected_mode,
    }
    assert "SDETKIT_CASSETTE" not in os.environ
    assert os.environ["SDETKIT_CASSETTE_MODE"] == "previous"


def test_cassette_get_reports_errors_as_usage_failures(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import sdetkit.cassette_get as cassette_get_module

    def _boom(args: list[str]) -> int:
        raise RuntimeError("cassette is unreadable")

    monkeypatch.setattr(cassette_get_module, "cassette_get", _boom)

    assert cli.main(["cassette-get", "https://example.test"]) == 2
    assert "cassette is unreadable" in capsys.readouterr().err


def test_unknown_command_and_missing_command_are_usage_errors(
    capsys: pytest.CaptureFixture[str],
) -> None:
    for argv in (["not-a-command"], []):
        with pytest.raises(SystemExit) as excinfo:
            cli.main(argv)
        assert excinfo.value.code == 2
    assert "usage: sdetkit" in capsys.readouterr().err


def test_version_flag_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--version"])
    assert excinfo.value.code == 0
    assert capsys.readouterr().out.strip() == cli.tool_version()


def test_run_module_main_calls_module_main(monkeypatch: pytest.MonkeyPatch) -> None:
    import sdetkit.kvcli as kvcli

    monkeypatch.setattr(kvcli, "main", lambda args: len(args))
    assert cli._run_module_main("sdetkit.kvcli", ["a", "b", "c"]) == 3


def _fake_doctor_main(payload: dict[str, object], rc: int = 0):
    def _main(args: list[str]) -> int:
        _main.args = list(args)  # type: ignore[attr-defined]
        print(json.dumps(payload))
        return rc

    return _main


def test_doctor_report_contract_writes_json_markdown_and_bundle(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import sdetkit.doctor as doctor_module

    fake = _fake_doctor_main({"ok": True, "checks": {}, "score": 100})
    monkeypatch.setattr(doctor_module, "main", fake)
    vector = tmp_path / "vector.json"
    vector.write_text(json.dumps({"schema_version": "fv", "failures": []}), encoding="utf-8")
    out = tmp_path / "report.json"
    bundle = tmp_path / "bundle"

    rc = cli.main(
        [
            "doctor",
            "--report-contract",
            "--json",
            f"--out={out}",
            "--report-artifact-dir",
            str(bundle),
            "--failure-vector-bundle",
            str(vector),
            "--dev",
        ]
    )

    assert rc == 0
    assert fake.args == ["--dev", "--format", "json", "--no-workspace"]  # type: ignore[attr-defined]
    printed = json.loads(capsys.readouterr().out)
    assert json.loads(out.read_text(encoding="utf-8")) == printed
    manifest = json.loads((bundle / "doctor-report-manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "sdetkit.doctor_report_artifact_bundle.v1"
    assert set(manifest["outputs"]) == {"json", "markdown", "failure_vector"}
    for name in ("doctor-report.json", "doctor-report.md", "failure-vector.json"):
        assert (bundle / name).is_file()


def test_doctor_report_contract_markdown_is_default_alias(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import sdetkit.doctor as doctor_module

    monkeypatch.setattr(doctor_module, "main", _fake_doctor_main({"ok": False}, rc=1))

    assert cli.main(["doctor", "--report-contract", "--format=markdown", "--no-workspace"]) == 1
    assert not capsys.readouterr().out.lstrip().startswith("{")


@pytest.mark.parametrize(
    "argv",
    [
        ["doctor", "--report-contract", "--format", "yaml"],
        ["doctor", "--report-contract", "--format"],
        ["doctor", "--report-contract", "--out"],
        ["doctor", "--report-contract", "--report-artifact-dir"],
        ["doctor", "--report-contract", "--failure-vector-bundle"],
    ],
)
def test_doctor_report_contract_rejects_bad_arguments(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(argv)
    assert excinfo.value.code == 2


def test_doctor_report_contract_handles_non_json_doctor_output(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import sdetkit.doctor as doctor_module

    def _main(args: list[str]) -> int:
        print("not json")
        return 0

    monkeypatch.setattr(doctor_module, "main", _main)

    assert cli.main(["doctor", "--report-contract"]) == 2
    assert "could not build report contract" in capsys.readouterr().err


def test_doctor_report_contract_rejects_unreadable_failure_vector(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import sdetkit.doctor as doctor_module

    monkeypatch.setattr(doctor_module, "main", _fake_doctor_main({"ok": True}))
    bad = tmp_path / "vector.json"
    bad.write_text("[1, 2]", encoding="utf-8")

    rc = cli.main(["doctor", "--report-contract", "--failure-vector-bundle", str(bad), "--json"])

    assert rc == 2
    assert "could not load FailureVector bundle" in capsys.readouterr().err


def test_doctor_without_report_contract_dispatches_normally(
    calls: list[tuple[str, list[str]]],
) -> None:
    assert cli.main(["doctor", "--json"]) == 7
    assert calls == [("sdetkit.doctor", ["--json"])]


@pytest.mark.parametrize(
    ("group", "subcommand", "module"),
    [
        (group, subcommand, module)
        for group, table in sorted(cli.SUBCOMMANDS.items())
        for subcommand, (module, _) in sorted(table.items())
    ],
)
def test_subcommand_groups_dispatch_to_their_module(
    group: str, subcommand: str, module: str, calls: list[tuple[str, list[str]]]
) -> None:
    assert cli.main([group, subcommand, "--x"]) == 7
    assert calls == [(module, ["--x"])]


@pytest.mark.parametrize("group", ["diagnose", "verify"])
def test_subcommand_group_help_lists_subcommands(
    group: str, calls: list[tuple[str, list[str]]], capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main([group, "--help"]) == 0
    out = capsys.readouterr().out
    for subcommand in cli.SUBCOMMANDS[group]:
        assert subcommand in out
    assert calls == []


@pytest.mark.parametrize("group", ["diagnose", "verify"])
def test_subcommand_group_rejects_unknown_subcommand(
    group: str, calls: list[tuple[str, list[str]]], capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main([group, "nope"]) == 2
    assert f"{group} error: expected a subcommand" in capsys.readouterr().err
    assert calls == []


def test_every_subcommand_module_exposes_main() -> None:
    import importlib

    for table in cli.SUBCOMMANDS.values():
        for module, _ in table.values():
            assert callable(importlib.import_module(module).main), module
