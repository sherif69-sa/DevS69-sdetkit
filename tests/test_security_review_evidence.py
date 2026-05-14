from __future__ import annotations

import json
from pathlib import Path

from sdetkit import security_review_evidence as security_review


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _review_threads(*threads: dict) -> dict:
    return {
        "data": {
            "repository": {
                "pullRequest": {
                    "reviewThreads": {
                        "nodes": list(threads),
                    }
                }
            }
        }
    }


def _thread(*, resolved: bool, body: str, author: str = "github-advanced-security") -> dict:
    return {
        "isResolved": resolved,
        "isOutdated": False,
        "path": "src/sdetkit/adaptive_diagnosis.py",
        "line": 1320,
        "comments": {
            "nodes": [
                {
                    "author": {"login": author},
                    "body": body,
                    "url": "https://github.example/review-comment",
                }
            ]
        },
    }


def test_security_review_evidence_emits_unresolved_security_finding(tmp_path: Path) -> None:
    path = _write_json(
        tmp_path / "review-threads.json",
        _review_threads(
            _thread(
                resolved=False,
                body="sdetkit-security-gate / High entropy string. Dismissing the alert will mark this conversation as resolved.",
            )
        ),
    )

    payload = security_review.build_security_review_evidence(path)

    assert payload["state"] == "warning"
    assert payload["active_threat_count"] == 1
    finding = payload["active_threats"][0]
    assert finding["risk_surface"] == "security"
    assert finding["review_first"] is True
    assert finding["safe_to_auto_fix"] is False
    assert finding["automation_allowed_now"] is False
    assert finding["owner_files"] == ["src/sdetkit/adaptive_diagnosis.py"]
    assert "requires action" in finding["title"].lower()
    assert "Fix the flagged surface or dismiss the false positive" in " ".join(
        finding["recommended_commands"]
    )


def test_security_review_evidence_ignores_resolved_threads(tmp_path: Path) -> None:
    path = _write_json(
        tmp_path / "review-threads.json",
        _review_threads(_thread(resolved=True, body="sdetkit-security-gate / High entropy string")),
    )

    payload = security_review.build_security_review_evidence(path)

    assert payload["state"] == "healthy"
    assert payload["active_threat_count"] == 0
    assert payload["active_threats"] == []


def test_security_review_evidence_ignores_non_security_review_threads(tmp_path: Path) -> None:
    path = _write_json(
        tmp_path / "review-threads.json",
        _review_threads(
            _thread(resolved=False, body="Please rename this helper.", author="reviewer")
        ),
    )

    payload = security_review.build_security_review_evidence(path)

    assert payload["state"] == "healthy"
    assert payload["active_threat_count"] == 0


def test_security_review_evidence_merges_with_sentinel_control_room(tmp_path: Path) -> None:
    review_threads = _write_json(
        tmp_path / "review-threads.json",
        _review_threads(
            _thread(resolved=False, body="github-advanced-security warning: security gate")
        ),
    )
    sentinel = _write_json(
        tmp_path / "control-room.json",
        {
            "schema_version": "sdetkit.adaptive.sentinel.control_room.v1",
            "state": "healthy",
            "active_threat_count": 0,
            "active_threats": [],
            "review_first_count": 0,
            "automation_allowed_now": False,
        },
    )

    security = security_review.build_security_review_evidence(review_threads)
    merged = security_review.merge_with_sentinel_control_room(sentinel, security)

    assert merged["state"] == "warning"
    assert merged["security_review_state"] == "review_required"
    assert merged["active_threat_count"] == 1
    assert merged["review_first_count"] == 1
    assert merged["active_threats"][0]["risk_surface"] == "security"
