from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

_MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "enforce_branch_protection.py"
_SPEC = importlib.util.spec_from_file_location("enforce_branch_protection", _MODULE_PATH)
assert _SPEC and _SPEC.loader
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)


def test_defaults_use_real_check_contexts_and_relaxed_review_policy(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def _fake_request(*, token: str, method: str, url: str, payload: dict[str, Any] | None = None) -> Any:
        captured["token"] = token
        captured["method"] = method
        captured["url"] = url
        captured["payload"] = payload
        return {}

    monkeypatch.setattr(_MOD, "_request", _fake_request)

    rc = _MOD.main([
        "--owner",
        "octo",
        "--repo",
        "hello",
        "--token",
        "x",
    ])

    assert rc == 0
    payload = captured["payload"]
    assert payload["required_status_checks"]["checks"] == [
        {"context": x} for x in _MOD.DEFAULT_REQUIRED_CHECKS
    ]
    assert payload["required_pull_request_reviews"]["required_approving_review_count"] == 1
    assert payload["required_pull_request_reviews"]["require_code_owner_reviews"] is False
    assert payload["enforce_admins"] is False


def test_cli_flags_override_review_policy_and_checks(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def _fake_request(*, token: str, method: str, url: str, payload: dict[str, Any] | None = None) -> Any:
        captured["payload"] = payload
        return {}

    monkeypatch.setattr(_MOD, "_request", _fake_request)

    rc = _MOD.main([
        "--owner",
        "octo",
        "--repo",
        "hello",
        "--token",
        "x",
        "--required-check",
        "A / one",
        "--required-check",
        "B / two",
        "--required-approving-review-count",
        "0",
        "--require-code-owner-reviews",
        "--enforce-admins",
    ])

    assert rc == 0
    payload = captured["payload"]
    assert payload["required_status_checks"]["checks"] == [
        {"context": "A / one"},
        {"context": "B / two"},
    ]
    assert payload["required_pull_request_reviews"]["required_approving_review_count"] == 0
    assert payload["required_pull_request_reviews"]["require_code_owner_reviews"] is True
    assert payload["enforce_admins"] is True


def test_dry_run_prints_payload_and_skips_request(monkeypatch, capsys) -> None:
    def _fake_request(**_: Any) -> Any:
        raise AssertionError("_request should not be called in dry-run mode")

    monkeypatch.setattr(_MOD, "_request", _fake_request)

    rc = _MOD.main([
        "--owner",
        "octo",
        "--repo",
        "hello",
        "--token",
        "x",
        "--dry-run",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "required_status_checks" in out
    assert "maintenance-autopilot / autopilot" in out
