from __future__ import annotations

import json
from pathlib import Path

from sdetkit import operator_evidence_loop as loop


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _failure_bundle(path: Path) -> Path:
    return _write_json(
        path,
        {
            "schema_version": "sdetkit.adaptive.failure_bundle.v1",
            "status": "review_required",
            "review_first": True,
            "safe_to_auto_fix": False,
            "primary_diagnosis_code": "PACKAGE_INSTALL_FAILURE",
            "primary_diagnosis_title": "Dependency resolver failed",
            "diagnosis_count": 1,
            "diagnosis_codes": ["PACKAGE_INSTALL_FAILURE"],
            "diagnoses": [
                {
                    "code": "PACKAGE_INSTALL_FAILURE",
                    "title": "Dependency resolver failed",
                    "diagnosis": "pip could not resolve constraints before proof.",
                    "severity": "high",
                    "confidence": "high",
                    "affected_files": ["constraints-ci.txt", "requirements-test.txt"],
                    "recommended_fix": ["Reproduce the exact install lane."],
                    "proof_commands": [
                        "python -m pip install -c constraints-ci.txt -r requirements-test.txt -e ."
                    ],
                }
            ],
        },
    )


def test_operator_evidence_loop_builds_review_first_handoff(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    quality = _write(
        tmp_path / "quality.log",
        "quality.sh cov passed\nTotal coverage: 96.69%\n",
    )
    failure_bundle = _failure_bundle(tmp_path / "failure-bundle.json")
    out_dir = tmp_path / "operator-loop"

    payload = loop.build_operator_evidence_loop(
        repo=repo,
        out_dir=out_dir,
        quality_log=quality,
        quality_outcome="success",
        failure_bundle=failure_bundle,
    )

    assert payload["schema_version"] == "sdetkit.operator.evidence_loop.v1"
    assert payload["classification"] == "review_required"
    assert payload["advisory_only"] is True
    assert payload["automation_boundary"] == {
        "dismisses_security_findings": False,
        "executes_patch_commands": False,
        "mutates_source": False,
        "pushes_or_merges": False,
    }

    patch_plan = payload["patch_plan"]
    assert patch_plan["enabled"] is True
    assert patch_plan["status"] == "review_required"
    assert patch_plan["source_kind"] == "evidence_graph"
    assert patch_plan["safe_to_auto_fix"] is False
    assert patch_plan["dry_run_only"] is True
    assert patch_plan["requires_human_review"] is True
    assert patch_plan["proof_commands"] == [
        "python -m pip install -c constraints-ci.txt -r requirements-test.txt -e ."
    ]
    assert patch_plan["recommended_commands"] == ["Reproduce the exact install lane."]

    artifacts = payload["artifacts"]
    for key in [
        "evidence_graph_json",
        "mission_control_json",
        "mission_control_markdown",
        "pr_quality_narrative_json",
        "pr_quality_narrative_markdown",
        "pr_quality_comment_markdown",
        "operator_loop_json",
        "operator_loop_markdown",
    ]:
        assert Path(artifacts[key]).exists(), key

    comment = Path(artifacts["pr_quality_comment_markdown"]).read_text(encoding="utf-8")
    assert "SDETKit Review Result: Green with evidence review" in comment
    assert "## Review-first patch plan" in comment
    assert "Source kind: `evidence_graph`" in comment
    assert "Safe to auto-fix: `false`" in comment
    assert "Dry run only: `true`" in comment
    assert "Requires human review: `true`" in comment
    assert "python -m pip install -c constraints-ci.txt -r requirements-test.txt -e ." in comment
    assert "Reproduce the exact install lane." in comment

    markdown = Path(artifacts["operator_loop_markdown"]).read_text(encoding="utf-8")
    assert "# Operator evidence loop" in markdown
    assert "Classification: `review_required`" in markdown
    assert "executes_patch_commands" not in markdown


def test_operator_evidence_loop_cli_writes_artifacts(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    quality = _write(
        tmp_path / "quality.log",
        "quality.sh cov passed\nTotal coverage: 96.69%\n",
    )
    failure_bundle = _failure_bundle(tmp_path / "failure-bundle.json")
    out_dir = tmp_path / "operator-loop"

    rc = loop.main(
        [
            "--repo",
            str(repo),
            "--out-dir",
            str(out_dir),
            "--quality-log",
            str(quality),
            "--quality-outcome",
            "success",
            "--failure-bundle",
            str(failure_bundle),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    stdout_payload = json.loads(capsys.readouterr().out)
    assert stdout_payload["classification"] == "review_required"
    assert stdout_payload["artifacts"]["operator_loop_json"].endswith("operator-loop.json")

    persisted = json.loads((out_dir / "operator-loop.json").read_text(encoding="utf-8"))
    assert persisted["classification"] == "review_required"
    assert (out_dir / "operator-loop.md").exists()
    assert (out_dir / "pr-quality-comment.md").exists()
