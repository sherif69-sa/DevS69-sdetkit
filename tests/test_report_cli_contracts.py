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
            code = cli.main(args)
        return Result(exit_code=code, stdout=stdout.getvalue(), stderr=stderr.getvalue())


def _write_run(path: Path, *, captured_at: str | None, findings: list[dict]) -> None:
    run = {
        "schema_version": "sdetkit.audit.run.v1",
        "tool_version": "0",
        "profile": "default",
        "packs": ["core"],
        "fail_on": "none",
        "findings": findings,
        "aggregates": {
            "counts_by_severity": {"error": 0, "info": 0, "warn": 0},
            "counts_fixable": 0,
            "counts_suppressed": 0,
        },
        "execution": {"incremental_used": False, "changed_file_count": 0},
    }
    if captured_at is not None:
        run["source"] = {"captured_at": captured_at}
    path.write_text(
        json.dumps(run, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


def test_report_ingest_is_deterministic_and_dedup(tmp_path: Path) -> None:
    runner = CliRunner()
    history = tmp_path / "history"
    r1 = tmp_path / "run1.json"
    r2 = tmp_path / "run2.json"

    _write_run(
        r1,
        captured_at="2020-01-01T00:00:00Z",
        findings=[
            {
                "fingerprint": "a",
                "rule_id": "r1",
                "severity": "warn",
                "message": "m",
                "path": "a.py",
            },
        ],
    )
    _write_run(
        r2,
        captured_at="2020-01-02T00:00:00Z",
        findings=[
            {
                "fingerprint": "b",
                "rule_id": "r2",
                "severity": "error",
                "message": "m",
                "path": "b.py",
            },
        ],
    )

    one = runner.invoke(
        ["report", "ingest", str(r1), "--history-dir", str(history), "--label", "first"]
    )
    assert one.exit_code == 0

    two = runner.invoke(
        ["report", "ingest", str(r2), "--history-dir", str(history), "--label", "second"]
    )
    assert two.exit_code == 0

    again = runner.invoke(
        ["report", "ingest", str(r1), "--history-dir", str(history), "--label", "first-again"]
    )
    assert again.exit_code == 0

    index_path = history / "index.json"
    assert index_path.exists()
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert index["schema_version"] == "sdetkit.audit.history.v1"
    runs = index["runs"]
    assert len(runs) == 2

    assert runs[0]["captured_at"] == "2020-01-01T00:00:00Z"
    assert runs[1]["captured_at"] == "2020-01-02T00:00:00Z"

    for row in runs:
        sha = row["sha256"]
        file = row["file"]
        assert isinstance(sha, str) and len(sha) == 64
        assert file == f"{sha}.json"
        assert (history / file).exists()


def test_report_diff_text_and_json_match_and_exit_codes(tmp_path: Path) -> None:
    runner = CliRunner()
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"

    _write_run(
        a,
        captured_at="2020-01-01T00:00:00Z",
        findings=[
            {
                "fingerprint": "x",
                "rule_id": "r1",
                "severity": "warn",
                "message": "m",
                "path": "a.py",
            },
        ],
    )
    _write_run(
        b,
        captured_at="2020-01-02T00:00:00Z",
        findings=[
            {
                "fingerprint": "x",
                "rule_id": "r1",
                "severity": "warn",
                "message": "m",
                "path": "a.py",
            },
            {
                "fingerprint": "y",
                "rule_id": "r2",
                "severity": "error",
                "message": "m",
                "path": "b.py",
            },
        ],
    )

    text = runner.invoke(
        [
            "report",
            "diff",
            "--from",
            str(a),
            "--to",
            str(b),
            "--format",
            "text",
            "--fail-on",
            "none",
        ]
    )
    assert text.exit_code == 0
    assert "NEW: 1" in text.stdout
    assert "RESOLVED: 0" in text.stdout

    warn = runner.invoke(
        [
            "report",
            "diff",
            "--from",
            str(a),
            "--to",
            str(b),
            "--format",
            "text",
            "--fail-on",
            "warn",
        ]
    )
    assert warn.exit_code == 1

    js = runner.invoke(
        [
            "report",
            "diff",
            "--from",
            str(a),
            "--to",
            str(b),
            "--format",
            "json",
            "--fail-on",
            "none",
        ]
    )
    assert js.exit_code == 0
    payload = json.loads(js.stdout)
    assert payload["counts"]["new"] == 1
    assert payload["counts"]["resolved"] == 0
    assert payload["counts"]["unchanged"] == 1


def test_report_diff_limit_new_applies_deterministically_to_text_and_json(tmp_path: Path) -> None:
    runner = CliRunner()
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"

    _write_run(a, captured_at="2020-01-01T00:00:00Z", findings=[])
    _write_run(
        b,
        captured_at="2020-01-02T00:00:00Z",
        findings=[
            {
                "fingerprint": "warn-rule",
                "rule_id": "r-warn",
                "severity": "warn",
                "message": "warn",
                "path": "warn.py",
            },
            {
                "fingerprint": "error-rule",
                "rule_id": "r-error",
                "severity": "error",
                "message": "error",
                "path": "error.py",
            },
            {
                "fingerprint": "info-rule",
                "rule_id": "r-info",
                "severity": "info",
                "message": "info",
                "path": "info.py",
            },
        ],
    )

    text = runner.invoke(
        [
            "report",
            "diff",
            "--from",
            str(a),
            "--to",
            str(b),
            "--format",
            "text",
            "--limit-new",
            "2",
        ]
    )
    assert text.exit_code == 0
    lines = [line for line in text.stdout.splitlines() if line.startswith("- [")]
    assert len(lines) == 2
    assert lines[0].startswith("- [error] r-error")
    assert lines[1].startswith("- [warn] r-warn")

    js = runner.invoke(
        [
            "report",
            "diff",
            "--from",
            str(a),
            "--to",
            str(b),
            "--format",
            "json",
            "--limit-new",
            "2",
        ]
    )
    assert js.exit_code == 0
    payload = json.loads(js.stdout)
    assert payload["counts"]["new"] == 3
    assert [item["fingerprint"] for item in payload["new"]] == ["error-rule", "warn-rule"]


def test_report_build_md_and_html_are_stable(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    history = tmp_path / "history"
    history.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1577836800")
    run1 = tmp_path / "run1.json"
    _write_run(
        run1,
        captured_at="2020-01-01T00:00:00Z",
        findings=[
            {
                "fingerprint": "a",
                "rule_id": "r1",
                "severity": "warn",
                "message": "m",
                "path": "a.py",
            },
        ],
    )
    assert (
        runner.invoke(["report", "ingest", str(run1), "--history-dir", str(history)]).exit_code == 0
    )

    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1577923200")
    run2 = tmp_path / "run2.json"
    _write_run(
        run2,
        captured_at="2020-01-02T00:00:00Z",
        findings=[
            {
                "fingerprint": "b",
                "rule_id": "r2",
                "severity": "error",
                "message": "m",
                "path": "b.py",
            },
        ],
    )
    assert (
        runner.invoke(["report", "ingest", str(run2), "--history-dir", str(history)]).exit_code == 0
    )

    out_md = tmp_path / "report.md"
    out_html = tmp_path / "report.html"

    first_md = runner.invoke(
        [
            "report",
            "build",
            "--history-dir",
            str(history),
            "--format",
            "md",
            "--output",
            str(out_md),
        ]
    )
    assert first_md.exit_code == 0
    md1 = out_md.read_text(encoding="utf-8")
    assert "# sdetkit audit trends" in md1
    assert "- runs: 2" in md1
    assert "## Top recurring rules" in md1
    assert "## Top paths" in md1

    second_md = runner.invoke(
        [
            "report",
            "build",
            "--history-dir",
            str(history),
            "--format",
            "md",
            "--output",
            str(out_md),
        ]
    )
    assert second_md.exit_code == 0
    md2 = out_md.read_text(encoding="utf-8")
    assert md1 == md2

    first_html = runner.invoke(
        [
            "report",
            "build",
            "--history-dir",
            str(history),
            "--format",
            "html",
            "--output",
            str(out_html),
        ]
    )
    assert first_html.exit_code == 0
    html1 = out_html.read_text(encoding="utf-8")
    assert "<h1>sdetkit audit trends</h1>" in html1
    assert "Runs: 2" in html1
    assert "<svg " in html1

    second_html = runner.invoke(
        [
            "report",
            "build",
            "--history-dir",
            str(history),
            "--format",
            "html",
            "--output",
            str(out_html),
        ]
    )
    assert second_html.exit_code == 0
    html2 = out_html.read_text(encoding="utf-8")
    assert html1 == html2


def test_report_recommend_supports_auto_detection_and_override(tmp_path: Path) -> None:
    runner = CliRunner()
    history = tmp_path / "history"
    history.mkdir(parents=True, exist_ok=True)

    run1 = tmp_path / "run1.json"
    _write_run(
        run1,
        captured_at="2020-01-01T00:00:00Z",
        findings=[
            {
                "fingerprint": "a",
                "rule_id": "api-timeout",
                "severity": "warn",
                "message": "API request timeout exceeds target",
                "path": "services/http_client.py",
                "tags": ["network"],
            },
        ],
    )
    assert (
        runner.invoke(["report", "ingest", str(run1), "--history-dir", str(history)]).exit_code == 0
    )

    run2 = tmp_path / "run2.json"
    _write_run(
        run2,
        captured_at="2020-01-02T00:00:00Z",
        findings=[
            {
                "fingerprint": "b",
                "rule_id": "api-retry",
                "severity": "error",
                "message": "HTTP response handling is missing retry policy",
                "path": "services/request_pipeline.py",
                "tags": ["api", "response"],
            },
        ],
    )
    assert (
        runner.invoke(["report", "ingest", str(run2), "--history-dir", str(history)]).exit_code == 0
    )

    text = runner.invoke(["report", "recommend", "--history-dir", str(history)])
    assert text.exit_code == 0
    assert "detected scenario: api-operations" in text.stdout
    assert "dashboard template: reliability_scorecard" in text.stdout

    js = runner.invoke(
        [
            "report",
            "recommend",
            "--history-dir",
            str(history),
            "--scenario",
            "compliance",
            "--format",
            "json",
        ]
    )
    assert js.exit_code == 0
    payload = json.loads(js.stdout)
    assert payload["detected_scenario"] == "api-operations"
    assert payload["active_scenario"] == "compliance"
    assert payload["dashboard_template"] == "compliance_posture"


def test_report_build_and_recommend_skip_unreadable_history_runs(tmp_path: Path) -> None:
    runner = CliRunner()
    history = tmp_path / "history"
    history.mkdir(parents=True, exist_ok=True)

    run1 = tmp_path / "run1.json"
    _write_run(
        run1,
        captured_at="2020-01-01T00:00:00Z",
        findings=[
            {
                "fingerprint": "a",
                "rule_id": "api-timeout",
                "severity": "warn",
                "message": "API request timeout exceeds target",
                "path": "services/http_client.py",
                "tags": ["network"],
            },
        ],
    )
    assert (
        runner.invoke(["report", "ingest", str(run1), "--history-dir", str(history)]).exit_code == 0
    )

    index_path = history / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["runs"].append(
        {
            "captured_at": "2020-01-02T00:00:00Z",
            "file": "broken.json",
            "label": "broken",
            "sha256": "f" * 64,
        }
    )
    index_path.write_text(
        json.dumps(index, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    (history / "broken.json").write_text("{not-json", encoding="utf-8")

    out_md = tmp_path / "report.md"
    build = runner.invoke(
        [
            "report",
            "build",
            "--history-dir",
            str(history),
            "--format",
            "md",
            "--output",
            str(out_md),
        ]
    )
    assert build.exit_code == 0
    assert "warning: skipping unreadable history run broken.json" in build.stderr
    assert "runs: 1" in out_md.read_text(encoding="utf-8")

    recommend = runner.invoke(["report", "recommend", "--history-dir", str(history)])
    assert recommend.exit_code == 0
    assert "warning: skipping unreadable history run broken.json" in recommend.stderr
    assert "runs analyzed: 1" in recommend.stdout
