from __future__ import annotations

import json

from sdetkit.current_head_failure_bundle import (
    SCHEMA_VERSION,
    build_current_head_failure_bundle,
    render_current_head_failure_bundle_markdown,
    write_current_head_failure_bundle,
)


def test_current_head_failure_bundle_persists_replayable_manifest(tmp_path):
    bundle = build_current_head_failure_bundle(
        pr_number=1366,
        head_sha="abc123",
        base_sha="def456",
        created_at="2026-05-21T03:00:00Z",
        check_intelligence={
            "checks_seen": 4,
            "failed_checks": [
                {
                    "name": "Validate (ubuntu-latest / py3.12)",
                    "safe_to_auto_fix": False,
                    "review_first": True,
                    "first_failure": {
                        "line": "FAILED tests/test_contract.py::test_contract",
                        "line_number": 42,
                        "tool": "pytest",
                        "kind": "test_failure",
                    },
                    "diagnosis": {
                        "owner_files": [
                            "src/sdetkit/check_intelligence.py",
                            "tests/test_check_intelligence_first_failure.py",
                        ]
                    },
                }
            ],
            "queued_checks": [{"name": "CI", "required": True}],
            "startup_failures": [],
            "missing_required_contexts": [],
        },
        action_report={"review_first": True, "safe_fix_available": False},
        diagnostic_vectors={"vectors": [{"classification": "test_failure"}]},
        remediation_plans={"plans": [{"classification": "review_first"}]},
        safe_fix_outcome={"attempted": False},
        refresh_summary={"merge_assessment": "blocked"},
    )

    written = write_current_head_failure_bundle(bundle, tmp_path)

    assert [path.name for path in written] == [
        "manifest.json",
        "failure-bundle.json",
        "failure-bundle.md",
    ]

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    payload = json.loads((tmp_path / "failure-bundle.json").read_text(encoding="utf-8"))
    markdown = (tmp_path / "failure-bundle.md").read_text(encoding="utf-8")

    assert manifest["schema_version"] == SCHEMA_VERSION
    assert manifest["pr_number"] == 1366
    assert manifest["head_sha"] == "abc123"
    assert manifest["base_sha"] == "def456"
    assert manifest["checks_seen"] == 4
    assert manifest["failed_checks"] == 1
    assert manifest["required_queued_checks"] == 1
    assert manifest["review_first"] is True
    assert manifest["safe_fix_allowed"] is False
    assert payload["first_failures"][0]["line"] == "FAILED tests/test_contract.py::test_contract"
    assert payload["owner_files"] == [
        "src/sdetkit/check_intelligence.py",
        "tests/test_check_intelligence_first_failure.py",
    ]
    assert "# Current-head failure evidence bundle" in markdown
    assert "Validate (ubuntu-latest / py3.12)" in markdown
    assert "src/sdetkit/check_intelligence.py" in markdown


def test_current_head_failure_bundle_rendering_is_deterministic():
    bundle = build_current_head_failure_bundle(
        pr_number=1,
        head_sha="head",
        base_sha="base",
        check_intelligence={"checks_seen": 0, "failed_checks": []},
        action_report={},
    )

    first = render_current_head_failure_bundle_markdown(bundle)
    second = render_current_head_failure_bundle_markdown(bundle)

    assert first == second
    assert "- Failed checks: `0`" in first
    assert "- none" in first
