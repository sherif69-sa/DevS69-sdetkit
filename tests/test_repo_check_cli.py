from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path

from sdetkit import cli


@dataclass
class Result:
    exit_code: int
    stdout: str
    stderr: str


class CliRunner:
    def invoke(self, args: list[str]) -> Result:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = cli.main(args)
        return Result(exit_code=exit_code, stdout=stdout.getvalue(), stderr=stderr.getvalue())


def _seed_one_trailing_ws(root: Path) -> None:
    (root / "bad.txt").write_text("abc \n", encoding="utf-8")


def test_repo_check_json_is_canonical_and_reports_trailing_ws(tmp_path: Path) -> None:
    _seed_one_trailing_ws(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        ["repo", "check", str(tmp_path), "--allow-absolute-path", "--format", "json"]
    )
    assert result.exit_code == 1
    assert result.stderr == ""

    payload = json.loads(result.stdout)
    assert list(payload.keys()) == ["findings", "metadata", "root", "summary"]
    assert payload["summary"]["findings"] == 1
    assert payload["summary"]["counts"]["warn"] == 1

    finding = payload["findings"][0]
    assert finding["check"] == "trailing_whitespace"
    assert finding["severity"] == "warn"
    assert finding["path"] == "bad.txt"
    assert finding["line"] == 1
    assert finding["column"] == 4
    assert finding["code"] == "trailing_ws"
    assert finding["message"] == "trailing whitespace"


def test_repo_check_md_includes_trailing_ws_line(tmp_path: Path) -> None:
    _seed_one_trailing_ws(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        ["repo", "check", str(tmp_path), "--allow-absolute-path", "--format", "md"]
    )
    assert result.exit_code == 1
    assert result.stderr == ""
    assert result.stdout.startswith("# sdetkit repo check report\n")
    assert "- `warn` `trailing_whitespace` `bad.txt:1:4` - trailing whitespace\n" in result.stdout


def test_repo_check_sarif_has_required_fields_and_location(tmp_path: Path) -> None:
    _seed_one_trailing_ws(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        ["repo", "check", str(tmp_path), "--allow-absolute-path", "--format", "sarif"]
    )
    assert result.exit_code == 1
    assert result.stderr == ""

    sarif = json.loads(result.stdout)
    assert sarif["version"] == "2.1.0"
    assert sarif["$schema"].endswith("sarif-2.1.0.json")
    assert sarif["runs"]
    run0 = sarif["runs"][0]
    assert run0["tool"]["driver"]["name"] == "sdetkit"
    assert run0["results"]

    loc = run0["results"][0]["locations"][0]["physicalLocation"]
    assert loc["artifactLocation"]["uri"] == "bad.txt"
    assert loc["region"]["startLine"] == 1
    assert loc["region"]["startColumn"] == 4


def test_repo_check_out_writes_file_and_matches_stdout(tmp_path: Path) -> None:
    _seed_one_trailing_ws(tmp_path)
    out = tmp_path / "out.json"

    runner = CliRunner()
    result = runner.invoke(
        [
            "repo",
            "check",
            str(tmp_path),
            "--allow-absolute-path",
            "--format",
            "json",
            "--out",
            str(out),
        ]
    )
    assert result.exit_code == 1
    assert result.stderr == ""
    assert out.read_text(encoding="utf-8") == result.stdout
