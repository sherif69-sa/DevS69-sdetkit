import json
from pathlib import Path

import pytest

from sdetkit.diagnostic_signal_snapshot import (
    QUIET_GREEN_STATUS,
    RATE_STATUS,
    build_snapshot,
    main,
    render_markdown,
)


def _narrative(*, nodes: int = 0, review_first: int = 0) -> dict[str, object]:
    return {
        "quality": {"ok": True},
        "graph": {"node_count": nodes, "review_first_count": review_first},
        "primary_signal": {"kind": "review_signal", "surface": "workflow"},
    }


def _worker(*, diagnoses: int = 0, review_first: int = 0) -> dict[str, object]:
    return {
        "summary": {
            "diagnosis_count": diagnoses,
            "review_first_count": review_first,
            "safe_fix_candidate_count": 0,
        },
        "decision_boundary": {
            "current_pr_decision_input": False,
            "patch_application_allowed": False,
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }


def _runtime(*, violations: int = 0) -> dict[str, object]:
    return {
        "isolated_proof": {
            "runtime_guard_passed": violations == 0,
            "runtime_guard_violation_count": violations,
        },
        "decision_boundary": {
            "current_pr_decision_input": False,
            "patch_application_allowed": False,
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }


def test_snapshot_records_quiet_green_baseline_without_claiming_false_positive_rate() -> None:
    snapshot = build_snapshot(
        evidence_narrative=_narrative(),
        evidence_graph={"nodes": []},
        diagnostic_worker_result=_worker(),
        runtime_proof_artifacts=_runtime(),
        security_finding_diagnosis={"diagnoses": [{"freshness": "stale"}]},
    )

    assert snapshot["status"] == QUIET_GREEN_STATUS
    assert snapshot["quiet_green_advisory_baseline"] is True
    measurements = snapshot["measurements"]
    assert measurements["primary_signal_kind"] == "review_signal"
    assert measurements["review_signal_present"] is True
    assert measurements["integration_proof_signal_present"] is False
    assert measurements["evidence_graph_node_count"] == 0
    assert measurements["diagnostic_worker_diagnosis_count"] == 0
    assert measurements["stale_security_finding_count"] == 1
    assert snapshot["kpi_readiness"]["advisor_false_positive_rate_status"] == RATE_STATUS
    assert snapshot["decision_boundary"]["automation_allowed"] is False


def test_snapshot_distinguishes_integration_proof_from_review_signal() -> None:
    narrative = _narrative()
    narrative["primary_signal"] = {"kind": "integration_proof", "surface": "tests"}
    snapshot = build_snapshot(
        evidence_narrative=narrative,
        evidence_graph={"nodes": []},
        diagnostic_worker_result=_worker(),
        runtime_proof_artifacts=_runtime(),
        security_finding_diagnosis={"diagnoses": []},
    )

    measurements = snapshot["measurements"]
    assert measurements["primary_signal_kind"] == "integration_proof"
    assert measurements["review_signal_present"] is False
    assert measurements["integration_proof_signal_present"] is True


def test_snapshot_records_observed_signal_without_granting_authority() -> None:
    snapshot = build_snapshot(
        evidence_narrative=_narrative(nodes=1, review_first=1),
        evidence_graph={"nodes": [{"review_first": True}]},
        diagnostic_worker_result=_worker(diagnoses=1, review_first=1),
        runtime_proof_artifacts=_runtime(),
        security_finding_diagnosis={"diagnoses": []},
    )

    assert snapshot["quiet_green_advisory_baseline"] is False
    assert snapshot["measurements"]["diagnostic_worker_review_first_count"] == 1
    assert snapshot["decision_boundary"]["current_pr_decision_input"] is False
    assert snapshot["decision_boundary"]["feeds_repo_memory"] is False


def test_snapshot_rejects_worker_authority_expansion() -> None:
    worker = _worker()
    worker["decision_boundary"]["automation_allowed"] = True

    with pytest.raises(ValueError, match="expands authority"):
        build_snapshot(
            evidence_narrative=_narrative(),
            evidence_graph={"nodes": []},
            diagnostic_worker_result=worker,
            runtime_proof_artifacts=_runtime(),
            security_finding_diagnosis={"diagnoses": []},
        )


def test_snapshot_markdown_keeps_baseline_and_boundary_explicit() -> None:
    snapshot = build_snapshot(
        evidence_narrative=_narrative(),
        evidence_graph={"nodes": []},
        diagnostic_worker_result=_worker(),
        runtime_proof_artifacts=_runtime(),
        security_finding_diagnosis={"diagnoses": []},
    )

    markdown = render_markdown(snapshot)
    assert "Diagnostic signal KPI snapshot" in markdown
    assert "Quiet green advisory baseline: `true`" in markdown
    assert "Primary narrative signal kind: `review_signal`" in markdown
    assert "Review signal present: `true`" in markdown
    assert "Integration proof signal present: `false`" in markdown
    assert "Advisor false-positive rate status: `requires_reviewed_history`" in markdown
    assert "Feeds RepoMemory: `false`" in markdown
    assert "Automation allowed: `false`" in markdown


def test_snapshot_cli_writes_json_and_markdown_artifacts(tmp_path: Path) -> None:
    paths: dict[str, Path] = {}
    payloads = {
        "evidence_narrative": _narrative(),
        "evidence_graph": {"nodes": []},
        "diagnostic_worker_result": _worker(),
        "runtime_proof_artifacts": _runtime(),
        "security_finding_diagnosis": {"diagnoses": []},
    }
    for name, payload in payloads.items():
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        paths[name] = path

    out_dir = tmp_path / "out"
    assert (
        main(
            [
                "--evidence-narrative",
                str(paths["evidence_narrative"]),
                "--evidence-graph",
                str(paths["evidence_graph"]),
                "--diagnostic-worker-result",
                str(paths["diagnostic_worker_result"]),
                "--runtime-proof-artifacts",
                str(paths["runtime_proof_artifacts"]),
                "--security-finding-diagnosis",
                str(paths["security_finding_diagnosis"]),
                "--out-dir",
                str(out_dir),
                "--format",
                "json",
            ]
        )
        == 0
    )
    assert (out_dir / "diagnostic-signal-snapshot.json").is_file()
    assert (out_dir / "diagnostic-signal-snapshot.md").is_file()
