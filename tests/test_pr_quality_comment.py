import json

from sdetkit import pr_quality_comment


def _payload(code="RUFF_FIXABLE_LINT", safe_to_auto_fix=True):
    return {
        "schema_version": "sdetkit.adaptive.diagnosis.v1",
        "ok": False,
        "status": "needs_fix",
        "risk_score": 26,
        "confidence": "high",
        "diagnoses": [
            {
                "code": code,
                "title": "Ruff fixable lint can be mechanically remediated",
                "why_developers_miss_it": "Developers often fix the visible import by hand.",
                "recommended_fix": ["Run ruff check --fix on affected files."],
                "proof_commands": ["PYTHONPATH=src python -m ruff check tests/test_example.py"],
            }
        ],
        "fix_plan": [
            {
                "code": code,
                "title": "Ruff fixable lint can be mechanically remediated",
                "safe_to_auto_fix": safe_to_auto_fix,
                "recommended_fix": ["Run ruff check --fix on affected files."],
                "proof_commands": ["PYTHONPATH=src python -m ruff check tests/test_example.py"],
            }
        ],
    }


def test_render_ruff_fixable_lint_comment_explains_auto_fix_route():
    rendered = pr_quality_comment.render_adaptive_diagnosis_comment(_payload())

    assert "### Adaptive Diagnosis" in rendered
    assert "diagnosis code: `RUFF_FIXABLE_LINT`" in rendered
    assert "Smallest safe fix:" in rendered
    assert "Run ruff check --fix on affected files." in rendered
    assert "Auto-fix status:" in rendered
    assert "SDETKit can auto-fix this only when" in rendered
    assert "F401/I001" in rendered
    assert "Logic-risk Ruff findings remain review-first." in rendered


def test_render_review_first_comment_when_fix_plan_is_not_safe():
    rendered = pr_quality_comment.render_adaptive_diagnosis_comment(
        _payload(code="PYTEST_ASSERTION_FAILURE", safe_to_auto_fix=False)
    )

    assert "diagnosis code: `PYTEST_ASSERTION_FAILURE`" in rendered
    assert "review-first" in rendered
    assert "Ruff fixable lint route:" not in rendered


def test_render_empty_for_green_or_monitor_payloads():
    payload = _payload()
    payload["status"] = "monitor"

    assert pr_quality_comment.render_adaptive_diagnosis_comment(payload) == ""


def test_cli_renders_comment_from_file(tmp_path, capsys):
    path = tmp_path / "adaptive-diagnosis.json"
    path.write_text(json.dumps(_payload()), encoding="utf-8")

    rc = pr_quality_comment.main([str(path)])

    assert rc == 0
    assert "Ruff fixable lint route:" in capsys.readouterr().out


def test_cli_rejects_bad_json(tmp_path, capsys):
    path = tmp_path / "adaptive-diagnosis.json"
    path.write_text("not-json", encoding="utf-8")

    rc = pr_quality_comment.main([str(path)])

    assert rc == 2
    assert "error=" in capsys.readouterr().out
