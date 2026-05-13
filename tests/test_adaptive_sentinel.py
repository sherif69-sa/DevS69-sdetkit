from __future__ import annotations

import json
from pathlib import Path

from sdetkit import adaptive_sentinel, cli

UNKNOWN_REVIEW_REQUIRED = "UNKNOWN" + "_REVIEW" + "_REQUIRED"


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _failure_bundle(root: Path, *, clear: bool = False) -> Path:
    return _write_json(
        root / "build/sdetkit/failure-intelligence/failure-intelligence-bundle.json",
        {
            "schema_version": "sdetkit.adaptive.failure_bundle.v1",
            "status": "clear" if clear else "needs_fix",
            "primary_diagnosis_code": "" if clear else UNKNOWN_REVIEW_REQUIRED,
            "diagnosis_count": 0 if clear else 1,
            "review_first": False if clear else True,
            "safe_to_auto_fix": False,
            "artifacts": {
                "operator_brief_markdown": (
                    root / "build/sdetkit/failure-intelligence/operator-brief.md"
                ).as_posix(),
            },
        },
    )


def test_sentinel_scan_flags_review_first_failure_bundle(tmp_path: Path) -> None:
    _failure_bundle(tmp_path)

    payload = adaptive_sentinel.build_sentinel_scan(root=tmp_path, write=True)

    assert payload["schema_version"] == "sdetkit.adaptive.sentinel.v1"
    assert payload["state"] == "critical"
    assert payload["ok"] is False
    assert payload["finding_count"] >= 1
    finding = payload["findings"][0]
    assert finding["source"] == "adaptive_failure_bundle"
    assert "review-first" in finding["summary"]
    joined = "\n".join(payload["recommendations"])
    assert "investigate failure" in joined
    assert "doctor --diagnose --failure-bundle" in joined
    assert (tmp_path / "build/sdetkit/sentinel/sentinel.json").exists()
    assert (tmp_path / "build/sdetkit/sentinel/sentinel.md").exists()
    assert (tmp_path / ".sdetkit/adaptive-sentinel/events.jsonl").exists()


def test_sentinel_scan_clear_bundle_is_healthy(tmp_path: Path) -> None:
    _failure_bundle(tmp_path, clear=True)

    payload = adaptive_sentinel.build_sentinel_scan(root=tmp_path, write=False)

    assert payload["state"] == "healthy"
    assert payload["ok"] is True
    assert payload["findings"][0]["source"] == "adaptive_failure_bundle"
    assert "status=clear" in payload["findings"][0]["evidence"]


def test_sentinel_cli_route_and_help(tmp_path: Path, capsys) -> None:
    _failure_bundle(tmp_path)

    rc = cli.main(
        [
            "adaptive",
            "sentinel",
            "scan",
            "--root",
            str(tmp_path),
            "--out-dir",
            str(tmp_path / "sentinel"),
            "--format",
            "json",
            "--no-fail",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["state"] == "critical"

    try:
        cli.main(["adaptive", "sentinel", "--help"])
    except SystemExit as exc:
        assert exc.code == 0
    help_out = capsys.readouterr().out
    assert "scan" in help_out
    assert "watch" in help_out


def test_sentinel_watch_writes_repeated_events(tmp_path: Path, capsys) -> None:
    _failure_bundle(tmp_path)
    event_log = tmp_path / "events.jsonl"

    rc = adaptive_sentinel.main(
        [
            "watch",
            "--root",
            str(tmp_path),
            "--out-dir",
            str(tmp_path / "sentinel"),
            "--event-log",
            str(event_log),
            "--interval-seconds",
            "0",
            "--iterations",
            "2",
            "--format",
            "json",
            "--no-fail",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["state"] == "critical"
    assert len(event_log.read_text(encoding="utf-8").splitlines()) == 2


def test_sentinel_render_markdown_contains_boundary(tmp_path: Path) -> None:
    _failure_bundle(tmp_path)
    payload = adaptive_sentinel.build_sentinel_scan(root=tmp_path, write=False)

    rendered = adaptive_sentinel.render_markdown(payload)

    assert "# Adaptive Sentinel" in rendered
    assert "Recommended next commands" in rendered
    assert "read-only" in rendered
