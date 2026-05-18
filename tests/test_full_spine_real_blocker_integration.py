from __future__ import annotations

import json
from pathlib import Path

from sdetkit import mission_control
from sdetkit import pr_quality_action_report as report
from sdetkit import pr_quality_evidence_narrative as narrative
from sdetkit.evidence_graph import build_evidence_graph, write_evidence_graph


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _assert_full_spine_blocker(
    *,
    tmp_path: Path,
    code: str,
    title: str,
    diagnosis: str,
    severity: str,
    expected_surface: str,
    proof_commands: list[str],
    recommended_fix: list[str],
    affected_files: list[str] | None = None,
) -> None:
    repo = tmp_path / f"repo-{expected_surface}"
    repo.mkdir()

    failure_bundle = _write_json(
        tmp_path / f"build/{expected_surface}/failure-bundle.json",
        {
            "schema_version": "sdetkit.adaptive.diagnosis.v1",
            "status": "review_required",
            "review_first": True,
            "safe_to_auto_fix": False,
            "primary_diagnosis_code": code,
            "diagnosis_count": 1,
            "diagnoses": [
                {
                    "code": code,
                    "title": title,
                    "diagnosis": diagnosis,
                    "severity": severity,
                    "confidence": "high",
                    "affected_files": affected_files or [],
                    "recommended_fix": recommended_fix,
                    "proof_commands": proof_commands,
                }
            ],
        },
    )

    graph = build_evidence_graph(failure_bundle=failure_bundle)
    graph_manifest = write_evidence_graph(
        graph,
        output_dir=tmp_path / f"build/{expected_surface}/evidence-graph",
    )
    graph_path = Path(graph_manifest["graph_path"])
    graph_payload = json.loads(graph_path.read_text(encoding="utf-8"))
    graph_node = graph_payload["nodes"][0]

    assert graph_node["source"] == "failure_bundle"
    assert graph_node["risk_surface"] == expected_surface
    assert graph_node["title"] == title
    assert graph_node["review_first"] is True
    assert graph_node["safe_to_auto_fix"] is False

    mission_out = tmp_path / f"build/{expected_surface}/mission-control"
    rc = mission_control.main(
        [
            "run",
            "--repo",
            str(repo),
            "--out-dir",
            str(mission_out),
            "--evidence-graph",
            str(graph_path),
            "--failure-bundle",
            str(failure_bundle),
            "--no-ledger",
        ]
    )

    assert rc == 0
    mission_bundle = json.loads((mission_out / "mission-control.json").read_text(encoding="utf-8"))
    mission_graph = mission_bundle["evidence_graph"]

    assert mission_bundle["decision"] == "SHIP_WITH_FINDINGS"
    assert mission_graph["top_blocker_surface"] == expected_surface
    assert mission_graph["top_blocker_title"] == title
    assert mission_graph["top_blocker_action"] == "review"

    for command in proof_commands:
        assert command in mission_graph["next_commands"]
    for command in recommended_fix:
        assert command in mission_graph["next_commands"]

    mission_markdown = (mission_out / "mission-control.md").read_text(encoding="utf-8")
    assert f"Top blocker: {title}" in mission_markdown
    assert f"Top blocker surface: {expected_surface}" in mission_markdown

    quality_log = _write(
        tmp_path / f"build/{expected_surface}/quality.log",
        "quality.sh cov passed\nTotal coverage: 96.69%\n",
    )
    security_control_room = _write_json(
        tmp_path / f"build/{expected_surface}/control-room-with-security-review.json",
        {
            "schema_version": "sdetkit.adaptive.sentinel.control_room.v1",
            "state": "healthy",
            "active_threat_count": 0,
            "active_threats": [],
            "review_first_count": 0,
            "automation_allowed_now": False,
            "security_review_collection_status": "collected",
            "security_review_finding_count": 0,
            "security_review_state": "healthy",
        },
    )

    pr_payload = narrative.build_narrative(
        quality_log=quality_log,
        quality_outcome="success",
        sentinel_control_room=security_control_room,
        evidence_graph=graph_path,
        failure_bundle=failure_bundle,
        changed_files=None,
    )
    pr_markdown = str(pr_payload["markdown"])

    assert pr_payload["primary_signal"]["kind"] == "review_signal"
    assert pr_payload["primary_signal"]["surface"] == expected_surface
    assert pr_payload["primary_signal"]["title"] == title
    assert pr_payload["graph"]["top_blocker"]["surface"] == expected_surface
    assert pr_payload["graph"]["top_blocker"]["title"] == title
    assert f"Evidence graph top blocker: {title} [{expected_surface}]." in pr_markdown
    assert "Security review evidence: collected; unresolved findings: 0." in pr_markdown

    for command in proof_commands:
        assert command in pr_markdown
    for command in recommended_fix:
        assert command in pr_markdown


def test_dependency_failure_flows_from_failure_bundle_to_graph_mission_control_and_pr_quality(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    failure_bundle = _write_json(
        tmp_path / "build/pr-quality/failure-intelligence/failure-bundle.json",
        {
            "schema_version": "sdetkit.adaptive.diagnosis.v1",
            "status": "review_required",
            "review_first": True,
            "safe_to_auto_fix": False,
            "primary_diagnosis_code": "PACKAGE_INSTALL_FAILURE",
            "diagnosis_count": 1,
            "diagnoses": [
                {
                    "code": "PACKAGE_INSTALL_FAILURE",
                    "title": "Dependency resolver failed",
                    "diagnosis": "pip could not resolve constraints before tests could prove behavior.",
                    "severity": "high",
                    "confidence": "high",
                    "affected_files": ["constraints-ci.txt", "requirements-test.txt"],
                    "recommended_fix": [
                        "Reproduce the exact install lane.",
                        "Align the smallest dependency surface instead of changing product code.",
                    ],
                    "proof_commands": [
                        "PYTHONPATH=src python -m pip install -c constraints-ci.txt -r requirements-test.txt -e ."
                    ],
                }
            ],
            "artifacts": {
                "operator_brief_markdown": str(
                    tmp_path / "build/pr-quality/failure-intelligence/operator-brief.md"
                ),
            },
        },
    )
    _write(
        tmp_path / "build/pr-quality/failure-intelligence/operator-brief.md",
        "# Operator brief\n\nDependency resolver failed.\n",
    )

    graph = build_evidence_graph(failure_bundle=failure_bundle)
    graph_manifest = write_evidence_graph(
        graph,
        output_dir=tmp_path / "build/sdetkit/evidence-graph",
    )
    graph_path = Path(graph_manifest["graph_path"])

    graph_payload = json.loads(graph_path.read_text(encoding="utf-8"))
    assert graph_payload["nodes"][0]["source"] == "failure_bundle"
    assert graph_payload["nodes"][0]["risk_surface"] == "dependency"
    assert graph_payload["nodes"][0]["title"] == "Dependency resolver failed"
    assert graph_payload["nodes"][0]["review_first"] is True
    assert graph_payload["nodes"][0]["safe_to_auto_fix"] is False

    mission_out = tmp_path / "build/mission-control"
    rc = mission_control.main(
        [
            "run",
            "--repo",
            str(repo),
            "--out-dir",
            str(mission_out),
            "--evidence-graph",
            str(graph_path),
            "--failure-bundle",
            str(failure_bundle),
            "--no-ledger",
        ]
    )
    assert rc == 0

    mission_bundle = json.loads((mission_out / "mission-control.json").read_text(encoding="utf-8"))
    mission_graph = mission_bundle["evidence_graph"]

    assert mission_bundle["decision"] == "SHIP_WITH_FINDINGS"
    assert mission_bundle["risk_band"] == "medium"
    assert mission_graph["status"] == "review_required"
    assert mission_graph["top_blocker_surface"] == "dependency"
    assert mission_graph["top_blocker_title"] == "Dependency resolver failed"
    assert mission_graph["top_blocker_action"] == "review"
    assert mission_graph["next_commands"] == [
        "PYTHONPATH=src python -m pip install -c constraints-ci.txt -r requirements-test.txt -e .",
        "Reproduce the exact install lane.",
        "Align the smallest dependency surface instead of changing product code.",
    ]

    mission_markdown = (mission_out / "mission-control.md").read_text(encoding="utf-8")
    assert "Top blocker: Dependency resolver failed" in mission_markdown
    assert "Top blocker surface: dependency" in mission_markdown
    assert "PYTHONPATH=src python -m pip install -c constraints-ci.txt" in mission_markdown

    quality_log = _write(
        tmp_path / "quality.log",
        "quality.sh cov passed\nTotal coverage: 96.69%\n",
    )
    security_control_room = _write_json(
        tmp_path / "build/sdetkit/sentinel/control-room-with-security-review.json",
        {
            "schema_version": "sdetkit.adaptive.sentinel.control_room.v1",
            "state": "healthy",
            "active_threat_count": 0,
            "active_threats": [],
            "review_first_count": 0,
            "automation_allowed_now": False,
            "security_review_collection_status": "collected",
            "security_review_finding_count": 0,
            "security_review_state": "healthy",
        },
    )

    pr_payload = narrative.build_narrative(
        quality_log=quality_log,
        quality_outcome="success",
        sentinel_control_room=security_control_room,
        evidence_graph=graph_path,
        failure_bundle=failure_bundle,
        changed_files=None,
    )

    pr_markdown = str(pr_payload["markdown"])

    assert pr_payload["quality"]["ok"] is True
    assert pr_payload["primary_signal"]["kind"] == "review_signal"
    assert pr_payload["primary_signal"]["surface"] == "dependency"
    assert pr_payload["primary_signal"]["title"] == "Dependency resolver failed"
    assert pr_payload["graph"]["top_blocker"]["surface"] == "dependency"
    assert pr_payload["graph"]["top_blocker"]["title"] == "Dependency resolver failed"
    assert "Evidence graph top blocker: Dependency resolver failed [dependency]." in pr_markdown
    assert "Security review evidence: collected; unresolved findings: 0." in pr_markdown
    assert "PYTHONPATH=src python -m pip install -c constraints-ci.txt" in pr_markdown
    assert "Reproduce the exact install lane." in pr_markdown


def test_security_failure_flows_through_full_spine(tmp_path: Path) -> None:
    _assert_full_spine_blocker(
        tmp_path=tmp_path,
        code="SECURITY_FINDING_REVIEW_REQUIRED",
        title="Security finding requires review",
        diagnosis="A security-sensitive finding must be reviewed before treating quality as the blocker.",
        severity="high",
        expected_surface="security",
        affected_files=["src/sdetkit/adaptive_diagnosis.py"],
        proof_commands=["PYTHONPATH=src python -m pre_commit run -a"],
        recommended_fix=[
            "Inspect the security finding and affected surface.",
            "Fix the finding or dismiss the false positive with a review reason.",
        ],
    )


def test_release_failure_flows_through_full_spine(tmp_path: Path) -> None:
    _assert_full_spine_blocker(
        tmp_path=tmp_path,
        code="RELEASE_ARTIFACT_INVALID",
        title="Release artifact validation failed",
        diagnosis="The release/package validation log shows an artifact contract failure.",
        severity="high",
        expected_surface="release",
        affected_files=["pyproject.toml"],
        proof_commands=[
            "PYTHONPATH=src python -m build && PYTHONPATH=src python -m twine check dist/*"
        ],
        recommended_fix=[
            "Rebuild the distribution artifacts from a clean tree.",
            "Run twine check before release publication.",
        ],
    )


def test_workflow_failure_flows_through_full_spine(tmp_path: Path) -> None:
    _assert_full_spine_blocker(
        tmp_path=tmp_path,
        code="WORKFLOW_CONTRACT_FAILURE",
        title="Workflow contract failed",
        diagnosis="The CI workflow contract failed before product behavior could be trusted.",
        severity="high",
        expected_surface="workflow",
        affected_files=[".github/workflows/pr-quality-comment.yml"],
        proof_commands=["PYTHONPATH=src python -m pre_commit run -a"],
        recommended_fix=[
            "Inspect the changed workflow contract.",
            "Validate the workflow YAML and required permission surface.",
        ],
    )


def test_cli_failure_flows_through_full_spine(tmp_path: Path) -> None:
    _assert_full_spine_blocker(
        tmp_path=tmp_path,
        code="CLI_CONTRACT_FAILURE",
        title="CLI contract failed",
        diagnosis="The command-line entry point failed before the operator path could be trusted.",
        severity="high",
        expected_surface="cli",
        affected_files=["src/sdetkit/cli.py"],
        proof_commands=["PYTHONPATH=src python -m sdetkit --help"],
        recommended_fix=[
            "Reproduce the failing CLI command.",
            "Repair the command contract before changing unrelated tests.",
        ],
    )


def test_docs_failure_flows_through_full_spine(tmp_path: Path) -> None:
    _assert_full_spine_blocker(
        tmp_path=tmp_path,
        code="DOCS_BUILD_CONTRACT",
        title="Docs build contract failed",
        diagnosis="The documentation build or navigation contract failed.",
        severity="high",
        expected_surface="docs",
        affected_files=["docs/index.md", "mkdocs.yml"],
        proof_commands=["PYTHONPATH=src mkdocs build --strict"],
        recommended_fix=[
            "Reproduce the strict docs build.",
            "Repair navigation or referenced document paths.",
        ],
    )


def test_tests_failure_flows_through_full_spine(tmp_path: Path) -> None:
    _assert_full_spine_blocker(
        tmp_path=tmp_path,
        code="PYTEST_ASSERTION_FAILURE",
        title="Behavior regression test failed",
        diagnosis="A targeted pytest assertion failed in a behavior-owned test.",
        severity="high",
        expected_surface="tests",
        affected_files=["tests/test_real_behavior.py"],
        proof_commands=[
            "PYTHONPATH=src python -m pytest -q tests/test_real_behavior.py::test_behavior -o addopts="
        ],
        recommended_fix=[
            "Inspect the failing assertion and changed behavior surface.",
            "Fix the product behavior or update the test only if the contract changed intentionally.",
        ],
    )


def test_secondary_blockers_flow_through_full_evidence_spine(tmp_path: Path) -> None:
    repo = tmp_path / "repo-secondary-blockers"
    repo.mkdir()

    failure_bundle = _write_json(
        tmp_path / "build/full-spine/failure-bundle.json",
        {
            "schema_version": "sdetkit.adaptive.failure_bundle.v1",
            "status": "review_required",
            "review_first": True,
            "safe_to_auto_fix": False,
            "primary_diagnosis_code": "SECURITY_FINDING_REVIEW_REQUIRED",
            "primary_diagnosis_title": "Security finding requires review",
            "diagnosis_count": 3,
            "diagnosis_codes": [
                "SECURITY_FINDING_REVIEW_REQUIRED",
                "PACKAGE_INSTALL_FAILURE",
                "COVERAGE_GATE_REGRESSION",
            ],
            "diagnoses": [
                {
                    "code": "SECURITY_FINDING_REVIEW_REQUIRED",
                    "title": "Security finding requires review",
                    "diagnosis": "A protected security surface changed and must be reviewed.",
                    "severity": "critical",
                    "confidence": "high",
                    "affected_files": ["src/sdetkit/adaptive_diagnosis.py"],
                    "recommended_fix": ["Review the unresolved security finding."],
                    "proof_commands": ["python -m sdetkit security check --root . --format json"],
                },
                {
                    "code": "PACKAGE_INSTALL_FAILURE",
                    "title": "Dependency resolver failed",
                    "diagnosis": "pip could not resolve constraints before tests could prove behavior.",
                    "severity": "high",
                    "confidence": "high",
                    "affected_files": ["constraints-ci.txt", "requirements-test.txt"],
                    "recommended_fix": ["Reproduce the exact install lane."],
                    "proof_commands": [
                        "python -m pip install -c constraints-ci.txt -r requirements-test.txt -e ."
                    ],
                },
                {
                    "code": "COVERAGE_GATE_REGRESSION",
                    "title": "Coverage gate regression",
                    "diagnosis": "Coverage dropped below the configured threshold.",
                    "severity": "warning",
                    "confidence": "medium",
                    "affected_files": ["src/sdetkit/example.py"],
                    "recommended_fix": ["Inspect the missing behavioral coverage."],
                    "proof_commands": ["bash quality.sh cov"],
                },
            ],
        },
    )

    graph = build_evidence_graph(failure_bundle=failure_bundle)
    graph_manifest = write_evidence_graph(
        graph,
        output_dir=tmp_path / "build/sdetkit/evidence-graph",
    )
    graph_path = Path(graph_manifest["graph_path"])
    graph_payload = json.loads(graph_path.read_text(encoding="utf-8"))

    graph_nodes_by_title = {node["title"]: node for node in graph_payload["nodes"]}
    assert set(graph_nodes_by_title) == {
        "Security finding requires review",
        "Dependency resolver failed",
        "Coverage gate regression",
    }
    assert graph_nodes_by_title["Security finding requires review"]["risk_surface"] == "security"
    assert graph_nodes_by_title["Dependency resolver failed"]["risk_surface"] == "dependency"
    assert graph_nodes_by_title["Coverage gate regression"]["risk_surface"] == "quality"

    mission_out = tmp_path / "build/mission-control"
    rc = mission_control.main(
        [
            "run",
            "--repo",
            str(repo),
            "--out-dir",
            str(mission_out),
            "--evidence-graph",
            str(graph_path),
            "--failure-bundle",
            str(failure_bundle),
            "--no-ledger",
        ]
    )
    assert rc == 0

    mission_bundle = json.loads((mission_out / "mission-control.json").read_text(encoding="utf-8"))
    mission_graph = mission_bundle["evidence_graph"]

    assert mission_graph["node_count"] == 3
    assert mission_graph["top_blocker_title"] == "Security finding requires review"
    assert mission_graph["top_blocker_surface"] == "security"
    assert mission_graph["top_blocker_review_first"] is True
    assert mission_graph["secondary_blocker_count"] == 2
    assert [item["title"] for item in mission_graph["secondary_blockers"]] == [
        "Dependency resolver failed",
        "Coverage gate regression",
    ]
    assert mission_graph["secondary_blockers"][0]["risk_surface"] == "dependency"
    assert mission_graph["secondary_blockers"][0]["next_commands"] == [
        "python -m pip install -c constraints-ci.txt -r requirements-test.txt -e .",
        "Reproduce the exact install lane.",
    ]

    mission_markdown = (mission_out / "mission-control.md").read_text(encoding="utf-8")
    assert "Secondary blockers: 2" in mission_markdown
    for blocker in mission_graph["secondary_blockers"]:
        assert (
            f"Secondary blocker: {blocker['title']} "
            f"[{blocker['risk_surface']}; {blocker['operator_action']}]" in mission_markdown
        )

    quality_log = _write(
        tmp_path / "quality.log",
        "quality.sh cov passed\nTotal coverage: 96.69%\n",
    )
    pr_payload = narrative.build_narrative(
        quality_log=quality_log,
        quality_outcome="success",
        sentinel_control_room=None,
        evidence_graph=graph_path,
        failure_bundle=failure_bundle,
        changed_files=None,
    )
    pr_markdown = str(pr_payload["markdown"])

    assert pr_payload["quality"]["ok"] is True
    assert pr_payload["primary_signal"]["kind"] == "review_signal"
    assert pr_payload["primary_signal"]["surface"] == "security"
    assert pr_payload["primary_signal"]["title"] == "Security finding requires review"
    assert pr_payload["graph"]["top_blocker"]["title"] == "Security finding requires review"
    assert pr_payload["graph"]["secondary_blocker_count"] == 2
    assert [item["title"] for item in pr_payload["graph"]["secondary_blockers"]] == [
        "Dependency resolver failed",
        "Coverage gate regression",
    ]
    assert pr_payload["graph"]["secondary_blockers"][0]["surface"] == "dependency"
    assert pr_payload["graph"]["secondary_blockers"][0]["next_proof"] == [
        "python -m pip install -c constraints-ci.txt -r requirements-test.txt -e .",
        "Reproduce the exact install lane.",
    ]

    assert "### Secondary graph blockers" in pr_markdown
    for blocker in pr_payload["graph"]["secondary_blockers"]:
        assert f"{blocker['title']} [{blocker['surface']}; {blocker['action']}]" in pr_markdown


def test_patch_plan_handoff_flows_through_full_evidence_spine(tmp_path: Path) -> None:
    repo = tmp_path / "repo-patch-plan-full-spine"
    repo.mkdir()

    failure_bundle = _write_json(
        tmp_path / "build/full-spine-patch-plan/failure-bundle.json",
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
                    "diagnosis": "pip could not resolve constraints before tests could prove behavior.",
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

    graph = build_evidence_graph(failure_bundle=failure_bundle)
    graph_manifest = write_evidence_graph(
        graph,
        output_dir=tmp_path / "build/full-spine-patch-plan/evidence-graph",
    )
    graph_path = Path(graph_manifest["graph_path"])

    mission_out = tmp_path / "build/full-spine-patch-plan/mission-control"
    rc = mission_control.main(
        [
            "run",
            "--repo",
            str(repo),
            "--out-dir",
            str(mission_out),
            "--evidence-graph",
            str(graph_path),
            "--failure-bundle",
            str(failure_bundle),
            "--no-ledger",
        ]
    )
    assert rc == 0

    mission_bundle_path = mission_out / "mission-control.json"
    mission_bundle = json.loads(mission_bundle_path.read_text(encoding="utf-8"))
    mission_patch_plan = mission_bundle["patch_plan"]

    assert mission_patch_plan["enabled"] is True
    assert mission_patch_plan["ok"] is True
    assert mission_patch_plan["status"] == "review_required"
    assert mission_patch_plan["source_kind"] == "evidence_graph"
    assert mission_patch_plan["source_code"] != "UNKNOWN"
    assert mission_patch_plan["safe_to_auto_fix"] is False
    assert mission_patch_plan["dry_run_only"] is True
    assert mission_patch_plan["requires_human_review"] is True
    assert mission_patch_plan["proof_commands"] == [
        "python -m pip install -c constraints-ci.txt -r requirements-test.txt -e ."
    ]
    assert mission_patch_plan["recommended_commands"] == ["Reproduce the exact install lane."]

    quality_log = _write(
        tmp_path / "quality.log",
        "quality.sh cov passed\nTotal coverage: 96.69%\n",
    )
    pr_payload = narrative.build_narrative(
        quality_log=quality_log,
        quality_outcome="success",
        sentinel_control_room=None,
        evidence_graph=graph_path,
        failure_bundle=failure_bundle,
        mission_control=mission_bundle_path,
        changed_files=None,
    )
    pr_markdown = str(pr_payload["markdown"])
    pr_patch_plan = pr_payload["patch_plan"]

    assert pr_patch_plan["enabled"] is True
    assert pr_patch_plan["source_kind"] == mission_patch_plan["source_kind"]
    assert pr_patch_plan["source_code"] == mission_patch_plan["source_code"]
    assert pr_patch_plan["safe_to_auto_fix"] is False
    assert pr_patch_plan["dry_run_only"] is True
    assert pr_patch_plan["requires_human_review"] is True
    assert pr_patch_plan["proof_commands"] == mission_patch_plan["proof_commands"]
    assert pr_patch_plan["recommended_commands"] == mission_patch_plan["recommended_commands"]

    assert "### Review-first patch plan" in pr_markdown
    assert "Source kind: `evidence_graph`" in pr_markdown
    assert f"Source code: `{mission_patch_plan['source_code']}`" in pr_markdown
    assert "Safe to auto-fix: `false`" in pr_markdown
    assert "Dry run only: `true`" in pr_markdown
    assert "Requires human review: `true`" in pr_markdown
    assert (
        "python -m pip install -c constraints-ci.txt -r requirements-test.txt -e ." in pr_markdown
    )
    assert "Reproduce the exact install lane." in pr_markdown

    action = {
        "status": "green",
        "primary_blocker": {},
        "automation": {"attempted": False, "allowed": False, "reason": "no remediation needed"},
        "recommended_actions": [],
        "proof_commands": [],
        "evidence": {},
    }
    intelligence = {
        "checks_seen": 44,
        "failed_checks": [],
        "queued_checks": [],
        "startup_failures": [],
        "security_review": {"collected": True, "unresolved_findings": 0},
    }

    body = report.render_comment_body(
        action_report=action,
        check_intelligence=intelligence,
        evidence_narrative=pr_payload,
    )

    assert "SDETKit Review Result: Green with evidence review" in body
    assert "## Review-first patch plan" in body
    assert "Source kind: `evidence_graph`" in body
    assert f"Source code: `{mission_patch_plan['source_code']}`" in body
    assert "Safe to auto-fix: `false`" in body
    assert "Dry run only: `true`" in body
    assert "Requires human review: `true`" in body
    assert "python -m pip install -c constraints-ci.txt -r requirements-test.txt -e ." in body
    assert "Reproduce the exact install lane." in body
