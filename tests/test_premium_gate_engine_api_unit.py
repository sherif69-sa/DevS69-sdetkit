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
