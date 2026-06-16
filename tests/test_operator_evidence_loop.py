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


def _artifact_key(*parts: str) -> str:
    return "_".join(parts)


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
        _artifact_key("evidence", "graph", "json"),
        _artifact_key("mission", "control", "json"),
        _artifact_key("mission", "control", "markdown"),
        _artifact_key("pr", "quality", "narrative", "json"),
        _artifact_key("pr", "quality", "narrative", "markdown"),
        _artifact_key("pr", "quality", "comment", "markdown"),
        _artifact_key("operator", "loop", "json"),
        _artifact_key("operator", "loop", "markdown"),
    ]:
        assert Path(artifacts[key]).exists(), key

    comment = Path(artifacts[_artifact_key("pr", "quality", "comment", "markdown")]).read_text(
        encoding="utf-8"
    )
    assert "SDETKit Review Result: Green with evidence review" in comment
    assert "<summary><strong>Review-first patch plan</strong></summary>" in comment
    assert "Source kind: `evidence_graph`" in comment
    assert "Safe to auto-fix: `false`" in comment
    assert "Dry run only: `true`" in comment
    assert "Requires human review: `true`" in comment
    assert "python -m pip install -c constraints-ci.txt -r requirements-test.txt -e ." in comment
    assert "Reproduce the exact install lane." in comment

    markdown = Path(artifacts[_artifact_key("operator", "loop", "markdown")]).read_text(
        encoding="utf-8"
    )
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
    assert stdout_payload["artifacts"][_artifact_key("operator", "loop", "json")].endswith(
        "operator-loop.json"
    )

    persisted = json.loads((out_dir / "operator-loop.json").read_text(encoding="utf-8"))
    assert persisted["classification"] == "review_required"
    assert (out_dir / "operator-loop.md").exists()
    assert (out_dir / "pr-quality-comment.md").exists()


def test_operator_evidence_loop_verification_marks_complete_bundle(tmp_path: Path) -> None:
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

    verification = payload["verification"]
    assert verification["ok"] is True
    assert verification["missing_artifacts"] == []
    assert verification["checks"] == {
        "advisory_boundary": True,
        "reporting_projection_boundary": True,
        "comment": True,
        "mission": True,
        "patch_plan": True,
        "required_artifacts": True,
    }

    markdown = (out_dir / "operator-loop.md").read_text(encoding="utf-8")
    assert "## Verification" in markdown
    assert "OK: `true`" in markdown
    assert "Missing artifacts: `0`" in markdown


def test_operator_evidence_loop_cli_verify_returns_success_for_complete_bundle(
    tmp_path: Path,
    capsys,
) -> None:
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
            "--verify",
        ]
    )

    assert rc == 0
    stdout_payload = json.loads(capsys.readouterr().out)
    assert stdout_payload["verification"]["ok"] is True
    persisted = json.loads((out_dir / "operator-loop.json").read_text(encoding="utf-8"))
    assert persisted["verification"]["ok"] is True


def test_operator_evidence_loop_surfaces_safe_fix_outcome_rollup(tmp_path: Path) -> None:
    graph_path = tmp_path / "evidence-graph.json"
    graph_path.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.evidence-graph.v1",
                "nodes": [],
                "source_summary": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    check_intelligence = tmp_path / "check-intelligence.json"
    check_intelligence.write_text(
        json.dumps(
            {
                "checks_seen": 1,
                "failed_checks": [
                    {
                        "name": "autopilot",
                        "safe_to_auto_fix": True,
                    }
                ],
                "queued_checks": [],
                "startup_failures": [],
                "security_review": {"collected": True, "unresolved_findings": 0},
                "safe_fix_outcome": {
                    "status": "pushed",
                    "attempted": True,
                    "remediation_ok": True,
                    "committed": True,
                    "pushed": True,
                    "affected_files": ["tests/test_example.py"],
                    "reason": "PR Quality safe-remediation bridge executed",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    out_dir = tmp_path / "operator-loop"
    payload = loop.build_operator_evidence_loop(
        repo=tmp_path,
        out_dir=out_dir,
        evidence_graph_path=graph_path,
        check_intelligence=check_intelligence,
        quality_outcome="success",
    )

    rollup = payload["safe_fix_outcome_rollup"]
    assert rollup["status"] == "pushed"
    assert rollup["pushed_count"] == 1
    assert rollup["recommendation"]["action"] == "rerun_proof"

    artifacts = payload["artifacts"]
    assert Path(artifacts[_artifact_key("safe", "fix", "outcome", "rollup", "json")]).exists()
    assert Path(artifacts[_artifact_key("safe", "fix", "outcome", "rollup", "markdown")]).exists()

    markdown = (out_dir / "operator-loop.md").read_text(encoding="utf-8")
    assert "## Safe-fix outcome rollup" in markdown
    assert "Recommendation: `rerun_proof`" in markdown
    assert "`tests/test_example.py`" in markdown


def _projection_inputs(
    tmp_path: Path,
) -> tuple[Path, Path, Path]:
    trajectory_path = _write_json(
        tmp_path / "trajectory-history.json",
        {
            "schema_version": ("sdetkit.trajectory_history_report.v1"),
            "record_count": 3,
            "review_first_count": 2,
            "auto_fix_allowed_count": 1,
            "by_final_result": {
                "passed": 2,
                "review_required": 1,
            },
            "by_risk_surface": {
                "formatting": 1,
                "security": 2,
            },
            "by_failure_class": {
                "formatting_only": 1,
                "security_review": 2,
            },
            "by_action": {
                "review": 2,
                "verify": 1,
            },
            "recent_decisions": [
                {
                    "diagnostic_id": "diag-3",
                    "action": "review",
                    "failure_class": ("security_review"),
                    "risk_surface": "security",
                    "review_first": True,
                    "auto_fix_allowed": False,
                    "final_result": ("review_required"),
                }
            ],
        },
    )
    patch_score_path = _write_json(
        tmp_path / "patch-score.json",
        {
            "schema_version": "sdetkit.patch_score.v1",
            "patch_id": "patch-1",
            "diagnosis_id": "diag-3",
            "failure_surface": "formatting",
            "classification": "formatting_only",
            "risk_level": "low",
            "strategy": "run_pre_commit",
            "score": 90,
            "minimum_score": 80,
            "changed_files": ["src/example.py"],
            "risk_flags": [
                {
                    "code": ("SAFE_PATTERN_NOT_REPEATED"),
                    "blocking": False,
                }
            ],
            "decision": {
                "status": ("candidate_for_protected_verification"),
                "candidate_for_protected_verification": (True),
                "automation_allowed": False,
            },
        },
    )
    verifier_path = _write_json(
        tmp_path / "protected-verifier.json",
        {
            "schema_version": ("sdetkit.protected_verifier.decision.v1"),
            "patch_id": "patch-1",
            "diagnosis_id": "diag-3",
            "patch_score": 90,
            "findings": [
                {
                    "code": ("SEMANTIC_EQUIVALENCE_NOT_PROVEN"),
                    "blocking": False,
                }
            ],
            "risk_flags": [],
            "decision": {
                "status": ("structurally_verified_candidate"),
                "structural_verification_passed": (True),
                "semantic_equivalence_proven": False,
                "automation_allowed": False,
                "merge_authorized": False,
            },
        },
    )
    return (
        trajectory_path,
        patch_score_path,
        verifier_path,
    )


def test_operator_loop_projects_existing_reports_without_changing_decision(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    graph_path = _write_json(
        tmp_path / "evidence-graph.json",
        {
            "schema_version": "sdetkit.evidence-graph.v1",
            "nodes": [],
            "source_summary": [],
        },
    )
    (
        trajectory_path,
        patch_score_path,
        verifier_path,
    ) = _projection_inputs(tmp_path)

    original_inputs = {
        path: path.read_text(encoding="utf-8")
        for path in (
            trajectory_path,
            patch_score_path,
            verifier_path,
        )
    }

    baseline = loop.build_operator_evidence_loop(
        repo=repo,
        out_dir=tmp_path / "baseline",
        evidence_graph_path=graph_path,
        quality_outcome="success",
    )
    projected = loop.build_operator_evidence_loop(
        repo=repo,
        out_dir=tmp_path / "projected",
        evidence_graph_path=graph_path,
        quality_outcome="success",
        trajectory_history=trajectory_path,
        patch_score=patch_score_path,
        protected_verifier_decision=verifier_path,
    )

    reporting_key = _artifact_key(
        "reporting",
        "projections",
    )
    trajectory_key = _artifact_key(
        "trajectory",
        "history",
        "projection",
    )
    patch_key = _artifact_key(
        "patch",
        "score",
        "projection",
    )
    verifier_key = _artifact_key(
        "protected",
        "verifier",
        "projection",
    )
    current_input_key = _artifact_key(
        "current",
        "pr",
        "decision",
        "input",
    )
    producer_changed_key = _artifact_key(
        "producer",
        "execution",
        "changed",
    )

    reporting = projected[reporting_key]

    assert reporting["schema_version"] == ".".join(
        (
            "sdetkit",
            "operator",
            "evidence",
            "loop",
            "reporting",
            "projections",
            "v1",
        )
    )
    assert reporting["reporting_only"] is True
    assert reporting[current_input_key] is False
    assert reporting[producer_changed_key] is False
    assert reporting["decision_boundary"] == {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "automatic_security_fix_allowed": False,
        "automatic_dismissal_allowed": False,
    }

    trajectory = reporting[trajectory_key]
    assert trajectory["collection_status"] == "collected"
    assert trajectory["record_count"] == 3
    assert trajectory["review_first_count"] == 2
    assert len(trajectory["recent_decisions"]) == 1

    patch_score = reporting[patch_key]
    assert patch_score["collection_status"] == "collected"
    assert patch_score["score"] == 90
    assert patch_score["source_candidate_for_protected_verification"] is True
    assert patch_score["source_automation_allowed"] is False

    verifier = reporting[verifier_key]
    assert verifier["collection_status"] == "collected"
    assert verifier["source_structural_verification_passed"] is True
    assert verifier["source_semantic_equivalence_proven"] is False

    assert projected["classification"] == baseline["classification"]
    projected_patch_plan = {
        key: value
        for key, value in projected["patch_plan"].items()
        if key not in {"path", "artifacts"}
    }
    baseline_patch_plan = {
        key: value
        for key, value in baseline["patch_plan"].items()
        if key not in {"path", "artifacts"}
    }
    assert projected_patch_plan == baseline_patch_plan
    assert projected["automation_boundary"] == baseline["automation_boundary"]
    assert projected["verification"]["ok"] is True

    artifacts = projected["artifacts"]
    assert (
        artifacts[
            _artifact_key(
                "trajectory",
                "history",
                "json",
            )
        ]
        == trajectory_path.as_posix()
    )
    assert artifacts[_artifact_key("patch", "score", "json")] == patch_score_path.as_posix()
    assert (
        artifacts[
            _artifact_key(
                "protected",
                "verifier",
                "json",
            )
        ]
        == verifier_path.as_posix()
    )

    markdown = (tmp_path / "projected" / "operator-loop.md").read_text(encoding="utf-8")
    assert "## Read-only reporting projections" in markdown
    assert "Current PR decision input: `false`" in markdown
    assert "Producer execution changed: `false`" in markdown
    assert "### Trajectory history" in markdown
    assert "### PatchScorer" in markdown
    assert "### ProtectedVerifier" in markdown

    for path, original in original_inputs.items():
        assert path.read_text(encoding="utf-8") == original


def test_operator_loop_cli_accepts_optional_projection_artifacts(
    tmp_path: Path,
    capsys,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    graph_path = _write_json(
        tmp_path / "evidence-graph.json",
        {
            "schema_version": "sdetkit.evidence-graph.v1",
            "nodes": [],
            "source_summary": [],
        },
    )
    (
        trajectory_path,
        patch_score_path,
        verifier_path,
    ) = _projection_inputs(tmp_path)
    out_dir = tmp_path / "operator-loop"

    rc = loop.main(
        [
            "--repo",
            str(repo),
            "--out-dir",
            str(out_dir),
            "--evidence-graph",
            str(graph_path),
            "--quality-outcome",
            "success",
            "--trajectory-history",
            str(trajectory_path),
            "--patch-score",
            str(patch_score_path),
            "--protected-verifier",
            str(verifier_path),
            "--format",
            "json",
            "--verify",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    reporting = payload[_artifact_key("reporting", "projections")]

    assert reporting["reporting_only"] is True
    assert (
        reporting[
            _artifact_key(
                "current",
                "pr",
                "decision",
                "input",
            )
        ]
        is False
    )
    assert (
        reporting[
            _artifact_key(
                "producer",
                "execution",
                "changed",
            )
        ]
        is False
    )
    assert payload["verification"]["ok"] is True
