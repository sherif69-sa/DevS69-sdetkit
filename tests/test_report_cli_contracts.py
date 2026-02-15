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


def test_report_diff_detects_changed_findings_with_same_fingerprint(tmp_path: Path) -> None:
    runner = CliRunner()
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"

    _write_run(
        a,
        captured_at="2020-01-01T00:00:00Z",
        findings=[
            {
                "fingerprint": "same-fp",
                "rule_id": "r1",
                "severity": "warn",
                "message": "message before",
                "path": "a.py",
                "tags": ["legacy"],
            }
        ],
    )
    _write_run(
        b,
        captured_at="2020-01-02T00:00:00Z",
        findings=[
            {
                "fingerprint": "same-fp",
                "rule_id": "r1",
                "severity": "error",
                "message": "message after",
                "path": "a.py",
                "tags": ["modern"],
            }
        ],
    )

    js = runner.invoke(["report", "diff", "--from", str(a), "--to", str(b), "--format", "json"])
    assert js.exit_code == 0
    payload = json.loads(js.stdout)
    assert payload["counts"]["new"] == 0
    assert payload["counts"]["resolved"] == 0
    assert payload["counts"]["unchanged"] == 0
    assert payload["counts"]["changed"] == 1
    assert payload["changed"] == [
        {
            "fingerprint": "same-fp",
            "changed_fields": ["severity", "message", "tags"],
            "from": {"severity": "warn", "rule_id": "r1", "path": "a.py"},
            "to": {"severity": "error", "rule_id": "r1", "path": "a.py"},
        }
    ]

    text = runner.invoke(["report", "diff", "--from", str(a), "--to", str(b), "--format", "text"])
    assert text.exit_code == 0
    assert "CHANGED: 1" in text.stdout
    assert "~ [warn->error] r1 a.py#same-fp fields=severity,message,tags" in text.stdout


def test_report_diff_fail_on_error_triggers_for_severity_regressions(tmp_path: Path) -> None:
    runner = CliRunner()
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"

    _write_run(
        a,
        captured_at="2020-01-01T00:00:00Z",
        findings=[
            {
                "fingerprint": "same",
                "rule_id": "r1",
                "severity": "warn",
                "message": "warn before",
                "path": "svc.py",
            },
        ],
    )
    _write_run(
        b,
        captured_at="2020-01-02T00:00:00Z",
        findings=[
            {
                "fingerprint": "same",
                "rule_id": "r1",
                "severity": "error",
                "message": "error now",
                "path": "svc.py",
            },
        ],
    )

    diff = runner.invoke(["report", "diff", "--from", str(a), "--to", str(b), "--fail-on", "error"])
    assert diff.exit_code == 1
    assert "CHANGED: 1" in diff.stdout


def test_report_diff_fail_on_ignores_non_severity_changes(tmp_path: Path) -> None:
    runner = CliRunner()
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"

    _write_run(
        a,
        captured_at="2020-01-01T00:00:00Z",
        findings=[
            {
                "fingerprint": "same",
                "rule_id": "r1",
                "severity": "error",
                "message": "before",
                "path": "svc.py",
            },
        ],
    )
    _write_run(
        b,
        captured_at="2020-01-02T00:00:00Z",
        findings=[
            {
                "fingerprint": "same",
                "rule_id": "r1",
                "severity": "error",
                "message": "after",
                "path": "svc.py",
            },
        ],
    )

    diff = runner.invoke(["report", "diff", "--from", str(a), "--to", str(b), "--fail-on", "error"])
    assert diff.exit_code == 0
    assert "CHANGED: 1" in diff.stdout


def test_report_diff_markdown_format_is_deterministic_and_honors_limit(tmp_path: Path) -> None:
    runner = CliRunner()
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"

    _write_run(
        a,
        captured_at="2020-01-01T00:00:00Z",
        findings=[
            {
                "fingerprint": "same",
                "rule_id": "r1",
                "severity": "warn",
                "message": "before",
                "path": "a.py",
            }
        ],
    )
    _write_run(
        b,
        captured_at="2020-01-02T00:00:00Z",
        findings=[
            {
                "fingerprint": "same",
                "rule_id": "r1",
                "severity": "error",
                "message": "after",
                "path": "a.py",
            },
            {
                "fingerprint": "new-error",
                "rule_id": "r2",
                "severity": "error",
                "message": "first",
                "path": "z.py",
            },
            {
                "fingerprint": "new-warn",
                "rule_id": "r3",
                "severity": "warn",
                "message": "second",
                "path": "b.py",
            },
        ],
    )

    result = runner.invoke(
        [
            "report",
            "diff",
            "--from",
            str(a),
            "--to",
            str(b),
            "--format",
            "md",
            "--limit-new",
            "1",
        ]
    )
    assert result.exit_code == 0
    assert result.stdout.startswith("# sdetkit audit diff\n")
    assert "## New findings" in result.stdout
    assert "new-error" in result.stdout
    assert "new-warn" not in result.stdout
    assert "## Changed findings" in result.stdout
    assert "warn→error" in result.stdout
    assert result.stdout.endswith("\n")


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


def test_report_recommend_markdown_format_outputs_structured_sections(tmp_path: Path) -> None:
    runner = CliRunner()
    history = tmp_path / "history"
    run_path = tmp_path / "run.json"

    _write_run(
        run_path,
        captured_at="2020-01-03T00:00:00Z",
        findings=[
            {
                "fingerprint": "one",
                "rule_id": "ci-alert",
                "severity": "warn",
                "message": "pipeline timeout in deployment stage",
                "path": "ops/deploy.yml",
                "tags": ["ops"],
            }
        ],
    )
    ingest = runner.invoke(["report", "ingest", str(run_path), "--history-dir", str(history)])
    assert ingest.exit_code == 0

    result = runner.invoke(
        [
            "report",
            "recommend",
            "--history-dir",
            str(history),
            "--scenario",
            "engineering",
            "--format",
            "md",
        ]
    )
    assert result.exit_code == 0
    assert result.stdout.startswith("# sdetkit workflow recommendations\n")
    assert "## Recommended helpers" in result.stdout
    assert "## Top recurring rules" in result.stdout
    assert "- ci-alert: 1" in result.stdout
    assert "## Top recurring paths" in result.stdout
    assert "- ops/deploy.yml: 1" in result.stdout
    assert result.stdout.endswith("\n")


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


def test_report_handles_corrupt_history_index_across_commands(tmp_path: Path) -> None:
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
    index_path.write_text("{not-json", encoding="utf-8")

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
    assert "warning: ignoring unreadable history index index.json" in build.stderr
    assert "No audit history found." in out_md.read_text(encoding="utf-8")

    recommend = runner.invoke(["report", "recommend", "--history-dir", str(history)])
    assert recommend.exit_code == 0
    assert "warning: ignoring unreadable history index index.json" in recommend.stderr
    assert "runs analyzed: 0" in recommend.stdout

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
                "tags": ["api"],
            },
        ],
    )

    ingest = runner.invoke(["report", "ingest", str(run2), "--history-dir", str(history)])
    assert ingest.exit_code == 0
    assert "warning: ignoring unreadable history index index.json" in ingest.stderr

    rewritten_index = json.loads(index_path.read_text(encoding="utf-8"))
    assert rewritten_index["schema_version"] == "sdetkit.audit.history.v1"
    assert len(rewritten_index["runs"]) == 1
    assert rewritten_index["runs"][0]["captured_at"] == "2020-01-02T00:00:00Z"
