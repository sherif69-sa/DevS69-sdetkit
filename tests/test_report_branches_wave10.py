from __future__ import annotations

import json
from pathlib import Path

import pytest

import sdetkit.report as r


def test_parse_captured_at_empty_invalid_and_naive_to_utc() -> None:
    assert r._parse_captured_at("") is None
    assert r._parse_captured_at("not-a-time") is None

    parsed = r._parse_captured_at("2025-01-01T00:00:00")
    assert parsed is not None
    assert parsed.tzinfo is not None
    assert parsed.isoformat().endswith("+00:00")

    parsed_z = r._parse_captured_at("2025-01-01T00:00:00Z")
    assert parsed_z is not None
    assert parsed_z.isoformat().endswith("+00:00")


def test_select_runs_window_validations_and_skips_bad_captured_at() -> None:
    runs = [{"source": {"captured_at": 123}}, {"source": {"captured_at": "nope"}}]

    with pytest.raises(ValueError, match="invalid --until-ts value"):
        r._select_runs_window(runs, since=None, since_ts=None, until_ts="bad")

    with pytest.raises(ValueError, match="--since-ts must be <= --until-ts"):
        r._select_runs_window(
            runs,
            since=None,
            since_ts="2025-01-02T00:00:00Z",
            until_ts="2025-01-01T00:00:00Z",
        )

    out = r._select_runs_window(
        runs,
        since=None,
        since_ts="2025-01-01T00:00:00Z",
        until_ts=None,
    )
    assert out == []


def test_tool_version_delegates_to_shared_versioning_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(r, "tool_version", lambda: "0+unknown")
    assert r._tool_version() == "0+unknown"


def test_captured_at_invalid_epoch_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "nope")
    assert r._captured_at() is None


def test_build_run_record_skips_non_dict_findings_and_sets_config_used_basename() -> None:
    payload = {
        "findings": [{"fingerprint": "fp1", "severity": "warn", "path": "a.py"}, "junk"],
        "suppressed": [],
    }
    run = r.build_run_record(
        payload,
        profile="default",
        packs=("core",),
        fail_on="none",
        repo_root="repo",
        config_used="/x/y/config.toml",
    )
    assert run["config_used"] == "config.toml"
    assert isinstance(run["findings"], list)
    assert len(run["findings"]) == 1
    assert run["findings"][0]["fingerprint"] == "fp1"


def test_coerce_run_record_upgrade_and_unsupported() -> None:
    doc = {"findings": [], "summary": {"profile": "p", "packs": ["core"]}, "root": "r"}
    out = r._coerce_run_record(doc)
    assert out["schema_version"] == r.RUN_SCHEMA
    assert out["profile"] == "p"

    with pytest.raises(ValueError, match="unsupported run record schema"):
        r._coerce_run_record({"x": 1})


def test_load_run_record_validations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pth = tmp_path / "run.json"

    pth.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    with pytest.raises(ValueError, match="run record must be an object"):
        r.load_run_record(pth)

    pth.write_text(json.dumps({"schema_version": "bad"}), encoding="utf-8")
    monkeypatch.setattr(r, "_coerce_run_record", lambda _d: {"schema_version": "bad"})
    with pytest.raises(ValueError, match="expected schema_version"):
        r.load_run_record(pth)


def test_findings_map_skips_non_dict() -> None:
    run = {"findings": [{"fingerprint": "a"}, "junk", {"fingerprint": "b"}]}
    m = r._findings_map(run)
    assert set(m) == {"a", "b"}


def test_render_diff_markdown_includes_none_for_empty_new_and_changed() -> None:
    payload = {
        "counts": {
            "new": 0,
            "resolved": 0,
            "unchanged": 0,
            "changed": 0,
            "new_by_severity": {"error": 0, "warn": 0, "info": 0},
        },
        "new": [],
        "changed": [],
    }
    md = r._render_diff_markdown(payload, limit=10)
    assert "## New findings" in md
    assert "## Changed findings" in md
    assert md.count("- none") == 2


def test_new_count_at_or_above_returns_0_when_counts_not_dict() -> None:
    payload = {"counts": {"new_by_severity": []}}
    assert r._new_count_at_or_above(payload, "warn") == 0


def test_summary_markdown_includes_diff_counts_and_actionable_list() -> None:
    run = {
        "findings": [
            {
                "fingerprint": "a",
                "severity": "error",
                "rule_id": "R1",
                "path": "a.py",
                "message": "m",
                "suppressed": False,
            },
            {
                "fingerprint": "b",
                "severity": "warn",
                "rule_id": "R2",
                "path": "b.py",
                "message": "m",
                "suppressed": True,
            },
        ]
    }
    diff = {"counts": {"new": 2, "resolved": 1}}
    out = r._summary_markdown(run, diff_payload=diff)
    assert "- NEW: 2" in out
    assert "- RESOLVED: 1" in out
    assert "Top actionable findings" in out
    assert "`R1`" in out


def test_history_runs_type_guards_and_sparkline_empty(tmp_path: Path) -> None:
    h = tmp_path / "history"
    h.mkdir()

    assert r._history_runs(h) == []

    (h / "index.json").write_text("{", encoding="utf-8")
    assert r._history_runs(h) == []

    (h / "index.json").write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    assert r._history_runs(h) == []

    (h / "index.json").write_text(json.dumps({"runs": "nope"}), encoding="utf-8")
    assert r._history_runs(h) == []

    (h / "index.json").write_text(json.dumps({"runs": [{"a": 1}, "junk"]}), encoding="utf-8")
    assert r._history_runs(h) == [{"a": 1}]

    assert r._sparkline([]) == ""
