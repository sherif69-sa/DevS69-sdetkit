from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit.cli import serve


def test_parse_review_request_normalizes_work_context_and_codescan() -> None:
    req = serve._parse_review_request(
        json.dumps(
            {
                "path": ".",
                "work_context": {"lane": 7, 2: "two"},
                "code_scan_json": " report.json ",
            }
        ).encode("utf-8")
    )

    assert req["work_context"] == {"lane": "7", "2": "two"}
    assert req["code_scan_json"] == "report.json"


def test_parse_review_request_rejects_invalid_no_workspace_type() -> None:
    with pytest.raises(serve.RequestValidationError, match="no_workspace"):
        serve._parse_review_request(
            json.dumps({"path": ".", "no_workspace": "false"}).encode("utf-8")
        )


def test_run_review_request_wraps_security_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_security(*_args, **_kwargs):
        raise serve.SecurityError("blocked")

    monkeypatch.setattr(serve, "safe_path", _raise_security)

    with pytest.raises(serve.RequestValidationError, match="Path rejected"):
        serve._run_review_request(
            {
                "path": ".",
                "workspace_root": ".sdetkit/workspace",
                "out_dir": None,
                "profile": "release",
                "no_workspace": True,
                "response_mode": "full",
                "work_id": "",
                "work_context": {},
                "code_scan_json": None,
            }
        )


def test_run_review_request_operator_summary_omits_payload_and_uses_default_out_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "repo"
    target.mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    def _safe_path(root: Path, raw: str, *, allow_absolute: bool = False) -> Path:
        p = Path(raw)
        return p if p.is_absolute() else (root / raw)

    called: dict[str, object] = {}

    def _fake_run_review(**kwargs):
        called.update(kwargs)
        out = Path(kwargs["out_dir"])
        out.mkdir(parents=True, exist_ok=True)
        json_path = out / "review.json"
        txt_path = out / "review.txt"
        json_path.write_text("{}", encoding="utf-8")
        txt_path.write_text("ok", encoding="utf-8")
        return (
            0,
            {
                "review_status": "pass",
                "status": "ok",
                "severity": "none",
                "profile": {"name": "release"},
                "contract_version": "x",
                "operator_summary": {"summary": "ok"},
                "workspace": {"run_hash": "abc"},
                "artifact_index": {"extra": "artifact"},
            },
            json_path,
            txt_path,
        )

    monkeypatch.setattr(serve, "safe_path", _safe_path)
    monkeypatch.setattr(serve.review, "run_review", _fake_run_review)

    resp = serve._run_review_request(
        {
            "path": str(target),
            "workspace_root": str(workspace),
            "out_dir": None,
            "profile": "release",
            "no_workspace": False,
            "response_mode": "operator-summary",
            "work_id": "ID-1",
            "work_context": {"lane": "ops"},
            "code_scan_json": "scan.json",
        }
    )

    result = resp["result"]
    assert resp["status"] == "ok"
    assert "payload" not in result
    assert result["workspace"]["run_hash"] == "abc"
    assert result["artifacts"]["extra"] == "artifact"
    assert Path(called["out_dir"]).as_posix().endswith(".sdetkit/review/repo")
    assert Path(called["code_scan_json"]).name == "scan.json"


def test_parse_positive_int_env_handles_non_positive_and_valid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SDETKIT_OBSERVABILITY_STALE_SECONDS", "0")
    assert serve._parse_positive_int_env("SDETKIT_OBSERVABILITY_STALE_SECONDS") is None

    monkeypatch.setenv("SDETKIT_OBSERVABILITY_STALE_SECONDS", " 15 ")
    assert serve._parse_positive_int_env("SDETKIT_OBSERVABILITY_STALE_SECONDS") == 15
