from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from sdetkit import premium_gate_engine as eng


def test_autolearn_from_payload_skips_invalid_recommendation_items(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    created: list[tuple[str, str, list[str], str]] = []

    def _fake_add_guideline(db_path: Path, title: str, body: str, tags: list[str], source: str = "") -> int:
        created.append((title, body, tags, source))
        return len(created)

    monkeypatch.setattr(eng, "add_guideline", _fake_add_guideline)

    ids = eng._autolearn_from_payload(
        tmp_path / "insights.db",
        {
            "recommendations": [
                "ignore",
                {"source": "doctor", "category": "policy", "message": "tighten rules", "severity": "high"},
                {"source": "", "category": "", "message": ""},
            ]
        },
    )

    assert ids == [1]
    assert created[0][0] == "doctor:policy"
    assert created[0][3] == "engine"


def test_insights_handler_read_payload_returns_empty_for_invalid_json() -> None:
    handler = object.__new__(eng._InsightsHandler)
    handler.headers = {"Content-Length": "8"}
    handler.rfile = io.BytesIO(b"not-json")

    assert handler._read_payload() == {}


def test_run_autofix_skips_non_dict_findings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "security-check.json").write_text(
        json.dumps(
            {
                "findings": [
                    "bad-item",
                    {"rule_id": "SEC_INFO", "severity": "info", "path": "a.py"},
                    {"rule_id": "SEC_X", "severity": "high", "path": "b.py"},
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        eng,
        "_apply_autofix_for_finding",
        lambda _root, finding: eng.AutoFixResult(str(finding.get("rule_id")), "b.py", "fixed", "ok"),
    )

    results = eng.run_autofix(tmp_path, tmp_path)

    assert len(results) == 1
    assert results[0].rule_id == "SEC_X"


def test_serve_insights_api_initializes_and_runs_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, object] = {}

    class _FakeServer:
        def __init__(self, addr, handler_cls):
            called["addr"] = addr
            called["handler_cls"] = handler_cls

        def serve_forever(self):
            called["served"] = True

    monkeypatch.setattr(eng, "_init_db", lambda db_path: called.setdefault("db", db_path))
    monkeypatch.setattr(eng.http.server, "ThreadingHTTPServer", _FakeServer)

    out_dir = tmp_path / "out"
    db_path = tmp_path / "insights.db"
    eng.serve_insights_api("127.0.0.1", 9090, out_dir, db_path)

    assert called["db"] == db_path
    assert called["addr"] == ("127.0.0.1", 9090)
    assert called["served"] is True
    assert eng._InsightsHandler.db_path == db_path
    assert eng._InsightsHandler.out_dir == out_dir


def test_insights_handler_read_payload_non_object_json_returns_empty() -> None:
    handler = object.__new__(eng._InsightsHandler)
    body = json.dumps([1, 2, 3]).encode("utf-8")
    handler.headers = {"Content-Length": str(len(body))}
    handler.rfile = io.BytesIO(body)

    assert handler._read_payload() == {}


def test_run_autofix_returns_skipped_when_security_payload_missing(tmp_path: Path) -> None:
    results = eng.run_autofix(tmp_path, tmp_path)
    assert len(results) == 1
    assert results[0].status == "skipped"
    assert "security-check.json" in results[0].message


def test_payload_helpers_handle_bool_string_and_invalid_values() -> None:
    payload = {"items": [1], "meta": {"ok": True}, "count_true": True, "count_text": "7", "count_bad": "x"}
    assert eng._payload_list(payload, "items") == [1]
    assert eng._payload_list(payload, "meta") == []
    assert eng._payload_dict(payload, "meta") == {"ok": True}
    assert eng._payload_dict(payload, "items") == {}
    assert eng._payload_int(payload, "count_true") == 1
    assert eng._payload_int(payload, "count_text") == 7
    assert eng._payload_int(payload, "count_bad", default=9) == 9


def test_apply_learned_guideline_actions_handles_missing_or_empty_db(tmp_path: Path) -> None:
    payload = {"warnings": [], "recommendations": [], "manual_fix_plan": []}

    missing_db = tmp_path / "missing.db"
    assert eng._apply_learned_guideline_actions(payload, missing_db) == payload

    empty_db = tmp_path / "empty.db"
    eng._init_db(empty_db)
    assert eng._apply_learned_guideline_actions(payload, empty_db) == payload


def test_apply_learned_guideline_actions_adds_recommendations_and_plan(tmp_path: Path) -> None:
    db_path = tmp_path / "learned.db"
    eng.add_guideline(db_path, "security:SEC_X", "rotate credentials", ["security", "critical"])

    payload = {
        "warnings": [
            {"source": "security", "category": "SEC_X", "severity": "critical", "message": "token leak"},
            "ignore",
        ],
        "recommendations": ["ignore-non-dict"],
        "manual_fix_plan": [],
    }

    updated = eng._apply_learned_guideline_actions(payload, db_path)

    recs = updated.get("recommendations", [])
    assert any(isinstance(item, dict) and item.get("category") == "learned-guideline" for item in recs)
    plan = updated.get("manual_fix_plan", [])
    assert any(isinstance(item, dict) and item.get("reason") == "Learned guideline match" for item in plan)
