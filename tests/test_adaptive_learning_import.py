from __future__ import annotations

import json
from pathlib import Path

from sdetkit import adaptive_learning_import
from sdetkit.cli import main as top_level_main


def _export(records: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema_version": "sdetkit.adaptive.enterprise_learning_export.v1",
        "ok": True,
        "record_count": len(records),
        "redaction_policy": {"placeholder": "<redacted>"},
        "records": records,
    }


def test_learning_import_accepts_redacted_export_and_emits_calibration_hints() -> None:
    payload = adaptive_learning_import.build_learning_import(
        _export(
            [
                {
                    "source_code": "RUFF_FIXABLE_LINT",
                    "outcome": "proof_passed",
                    "repo": "<redacted>",
                    "affected_files": ["<redacted>"],
                    "source_path": "<redacted>",
                },
                {
                    "source_code": "PYTEST_ASSERTION_FAILURE",
                    "outcome": "proof_failed",
                    "repository": "<redacted>",
                    "files": ["<redacted>"],
                },
            ]
        )
    )

    assert payload["ok"] is True
    assert payload["recommendation"] == "IMPORT"
    hints = {row["scenario_code"]: row for row in payload["calibration_hints"]}
    assert hints["RUFF_FIXABLE_LINT"]["action"] == "promote"
    assert hints["PYTEST_ASSERTION_FAILURE"]["action"] == "review_guardrail"


def test_learning_import_rejects_private_fields_and_raw_paths() -> None:
    payload = adaptive_learning_import.build_learning_import(
        _export(
            [
                {
                    "source_code": "RUFF_FIXABLE_LINT",
                    "repo": "private-repo",
                    "affected_files": ["src/private_widget.py"],
                    "evidence": "failure in /home/alice/work/private/tests/test_widget.py",
                }
            ]
        )
    )

    assert payload["ok"] is False
    assert payload["recommendation"] == "REJECT_IMPORT"
    codes = {row["code"] for row in payload["findings"]}
    assert "PRIVATE_FIELD_NOT_REDACTED" in codes
    assert "PRIVATE_IDENTIFIER_PATTERN" in codes
    assert payload["calibration_hint_count"] == 0




def test_learning_import_rejects_private_urls_hosts_and_emails() -> None:
    payload = adaptive_learning_import.build_learning_import(
        _export(
            [
                {
                    "source_code": "PYTEST_ASSERTION_FAILURE",
                    "repo": "<redacted>",
                    "affected_files": ["<redacted>"],
                    "issue_url": "https://github.example.internal/acme/private-repo/issues/123",
                    "hostname": "ci-runner-17.internal.example.com",
                    "owner": "alice@example.internal",
                }
            ]
        )
    )

    assert payload["ok"] is False
    assert payload["recommendation"] == "REJECT_IMPORT"
    codes = {row["code"] for row in payload["findings"]}
    assert "PRIVATE_FIELD_NOT_REDACTED" in codes
    assert "PRIVATE_URL_PATTERN" in codes
    assert "PRIVATE_HOSTNAME_PATTERN" in codes
    assert "PRIVATE_EMAIL_PATTERN" in codes

def test_learning_import_cli_and_top_level_passthrough(tmp_path: Path) -> None:
    export = tmp_path / "learning-export.json"
    out = tmp_path / "import-result.json"
    export.write_text(
        json.dumps(
            _export(
                [
                    {
                        "source_code": "PRE_COMMIT_FORMAT_DRIFT",
                        "outcome": "proof_passed",
                        "repo": "<redacted>",
                        "affected_files": ["<redacted>"],
                    }
                ]
            )
        ),
        encoding="utf-8",
    )

    rc = top_level_main(
        [
            "adaptive",
            "learning-import",
            str(export),
            "--format",
            "json",
            "--out",
            str(out),
        ]
    )

    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["calibration_hints"][0]["scenario_code"] == "PRE_COMMIT_FORMAT_DRIFT"
