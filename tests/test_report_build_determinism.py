from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli

RUN_SCHEMA = "sdetkit.audit.run.v1"


def _finding(*, rule_id: str, severity: str, path: str, message: str, fingerprint: str) -> dict:
    return {
        "rule_id": rule_id,
        "title": rule_id,
        "severity": severity,
        "path": path,
        "message": message,
        "fingerprint": fingerprint,
        "pack": "core",
        "fixable": False,
        "suppressed": False,
    }


def _write_run(p: Path, *, captured_at: str, findings: list[dict], err: int, warn: int) -> None:
    doc = {
        "schema_version": RUN_SCHEMA,
        "tool_version": "0.0.0",
        "profile": "default",
        "packs": ["core"],
        "fail_on": "none",
        "findings": findings,
        "aggregates": {
            "counts_by_severity": {"error": err, "warn": warn, "info": 0},
            "counts_suppressed": 0,
            "counts_fixable": 0,
        },
        "source": {"captured_at": captured_at},
        "execution": {"incremental_used": False, "changed_file_count": 0},
    }
    p.write_text(
        json.dumps(doc, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


def _ingest(history_dir: Path, run_json: Path, label: str) -> None:
    rc = cli.main(
        ["report", "ingest", str(run_json), "--history-dir", str(history_dir), "--label", label]
    )
    assert rc == 0


def _build(history_dir: Path, out: Path, fmt: str) -> str:
    rc = cli.main(
        [
            "report",
            "build",
            "--history-dir",
            str(history_dir),
            "--output",
            str(out),
            "--format",
            fmt,
        ]
    )
    assert rc == 0
    return out.read_text(encoding="utf-8")


def _reverse_index(history_dir: Path) -> None:
    idx = history_dir / "index.json"
    doc = json.loads(idx.read_text(encoding="utf-8"))
    assert isinstance(doc, dict)
    runs = doc.get("runs")
    assert isinstance(runs, list)
    doc["runs"] = list(reversed(runs))
    idx.write_text(
        json.dumps(doc, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


def test_report_build_is_deterministic_for_html_and_md(tmp_path: Path) -> None:
    history = tmp_path / "hist"
    history.mkdir()

    run1 = tmp_path / "run1.json"
    run2 = tmp_path / "run2.json"

    _write_run(
        run1,
        captured_at="2026-02-14T00:00:00Z",
        findings=[
            _finding(
                rule_id="R<one>&", severity="warn", path="a<b>.py", message="m1", fingerprint="fp1"
            ),
        ],
        err=0,
        warn=1,
    )
    _write_run(
        run2,
        captured_at="2026-02-14T00:00:01Z",
        findings=[
            _finding(
                rule_id="R<one>&", severity="warn", path="a<b>.py", message="m1", fingerprint="fp1"
            ),
            _finding(rule_id="R2", severity="error", path="x.py", message="m2", fingerprint="fp2"),
        ],
        err=1,
        warn=1,
    )

    _ingest(history, run1, "first")
    _ingest(history, run2, "second")

    _reverse_index(history)

    out_html = tmp_path / "report.html"
    html1 = _build(history, out_html, "html")
    html2 = _build(history, out_html, "html")
    assert html1 == html2
    assert "<p>Latest actionable findings: 2</p>" in html1
    assert "R<one>&" not in html1
    assert "a<b>.py" not in html1
    assert "R&lt;one&gt;&amp;" in html1
    assert "a&lt;b&gt;.py" in html1

    out_md = tmp_path / "report.md"
    md1 = _build(history, out_md, "md")
    md2 = _build(history, out_md, "md")
    assert md1 == md2
    assert md1.endswith("\n")
    assert "- latest actionable findings: 2" in md1
    assert "`R<one>&`" in md1
    assert "`a<b>.py`" in md1
