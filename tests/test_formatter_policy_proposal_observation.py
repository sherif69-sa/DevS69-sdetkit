from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from sdetkit import formatter_policy_proposal as proposal
from sdetkit import formatter_policy_proposal_observation as observation

HEAD = "a" * 40
REPO = "sherif69-sa/DevS69-sdetkit"
PR_NUMBER = 2142
CONTRACT = Path("docs/contracts/formatter-policy-proposal-observation.v1.json")
METRICS = {
    "exact_evidence_binding": "pass",
    "proposal_scope_clarity": "pass",
    "proof_plan_actionability": "pass",
    "rollback_clarity": "pass",
    "authority_boundary_preservation": "pass",
    "operator_usefulness": "pass",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _proposal(root: Path) -> Path:
    path = root / "evidence" / "formatter-policy-proposal.json"
    path.parent.mkdir(parents=True)
    payload = {
        "schema_version": proposal.SCHEMA_VERSION,
        "status": "passed",
        "proposal_status": "eligible_for_human_policy_proposal",
        "candidate_family": "formatter_only",
        "proposal_eligible": True,
        "execution_eligible": False,
        "branch_execution_allowed": False,
        "safe_fix_allowed": False,
        "review_required": True,
        "safety_gate_policy_changed": False,
        "source_repository": REPO,
        "source_commit_sha": HEAD,
        "source_pr_number": PR_NUMBER,
        **observation.authority_boundary(),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _observations(
    root: Path,
    proposal_path: Path,
    *,
    items: list[dict[str, object]] | None = None,
) -> Path:
    if items is None:
        items = [
            {
                "observation_id": "formatter-proposal-reviewed-001",
                "proposal_path": proposal_path.relative_to(root).as_posix(),
                "proposal_sha256": _sha256(proposal_path),
                "source_repository": REPO,
                "source_commit_sha": HEAD,
                "source_pr_number": PR_NUMBER,
                "reviewer_id": "maintainer@example.invalid",
                "reviewed_at": "2026-07-21T03:00:00Z",
                "decision": "accept",
                "decision_reason": "The proposal is clear and remains review-first.",
                "metric_outcomes": dict(METRICS),
                "review_notes": "Reviewed for observation only; no execution authority granted.",
            }
        ]
    path = root / "source" / "reviewed-observations.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": observation.OBSERVATIONS_SCHEMA_VERSION,
                "observations": items,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _build(root: Path, observations_path: Path) -> dict[str, object]:
    return observation.build_report(
        observations_path,
        contract_json=CONTRACT.resolve(),
        root=root,
        current_head_sha="b" * 40,
        generator_path=Path(observation.__file__),
    )


def test_formatter_proposal_observation_reports_reviewed_quality_without_execution(
    tmp_path: Path,
) -> None:
    proposal_path = _proposal(tmp_path)
    observations_path = _observations(tmp_path, proposal_path)

    report = _build(tmp_path, observations_path)

    assert report["schema_version"] == observation.SCHEMA_VERSION
    assert report["report_status"] == "reviewed_observations_available"
    assert report["reviewed_observation_count"] == 1
    assert report["decision_counts"]["accept"] == 1
    assert report["failed_metric_ids"] == []
    assert report["false_authority_count"] == 0
    assert report["execution_research_ready"] is False
    assert report["branch_execution_lane_active"] is False
    assert report["broader_maturity_claim_allowed"] is False
    assert report["observations_authorize_current_action"] is False
    assert report["automation_allowed"] is False
    assert report["patch_application_allowed"] is False
    assert report["merge_authorized"] is False
    assert report["publication_authorized"] is False
    assert report["security_dismissal_allowed"] is False
    assert report["semantic_equivalence_proven"] is False


def test_formatter_proposal_observation_writes_outputs_without_mutating_sources(
    tmp_path: Path,
) -> None:
    proposal_path = _proposal(tmp_path)
    observations_path = _observations(tmp_path, proposal_path)
    before = observations_path.read_bytes()

    report = observation.write_report(
        observations_path,
        out_dir=tmp_path / "out",
        contract_json=CONTRACT.resolve(),
        root=tmp_path,
        current_head_sha="b" * 40,
        generator_path=Path(observation.__file__),
    )

    assert observations_path.read_bytes() == before
    assert json.loads((tmp_path / "out" / observation.REPORT_JSON).read_text()) == report
    markdown = (tmp_path / "out" / observation.REPORT_MD).read_text()
    assert "Execution research ready: `false`" in markdown
    assert "Branch execution lane active: `false`" in markdown


def test_formatter_proposal_observation_rejects_stale_digest(tmp_path: Path) -> None:
    proposal_path = _proposal(tmp_path)
    observations_path = _observations(tmp_path, proposal_path)
    payload = json.loads(observations_path.read_text())
    payload["observations"][0]["proposal_sha256"] = "0" * 64
    observations_path.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="proposal digest is stale"):
        _build(tmp_path, observations_path)


def test_formatter_proposal_observation_rejects_authority_expansion(tmp_path: Path) -> None:
    proposal_path = _proposal(tmp_path)
    payload = json.loads(proposal_path.read_text())
    payload["patch_application_allowed"] = True
    proposal_path.write_text(json.dumps(payload))
    observations_path = _observations(tmp_path, proposal_path)

    with pytest.raises(ValueError, match="explicitly deny authority"):
        _build(tmp_path, observations_path)


def test_formatter_proposal_observation_rejects_source_mismatch(tmp_path: Path) -> None:
    proposal_path = _proposal(tmp_path)
    observations_path = _observations(tmp_path, proposal_path)
    payload = json.loads(observations_path.read_text())
    payload["observations"][0]["source_pr_number"] = PR_NUMBER + 1
    observations_path.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="source_pr_number"):
        _build(tmp_path, observations_path)


def test_formatter_proposal_observation_rejects_missing_metric(tmp_path: Path) -> None:
    proposal_path = _proposal(tmp_path)
    observations_path = _observations(tmp_path, proposal_path)
    payload = json.loads(observations_path.read_text())
    del payload["observations"][0]["metric_outcomes"]["operator_usefulness"]
    observations_path.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="every contracted metric"):
        _build(tmp_path, observations_path)


def test_formatter_proposal_observation_empty_source_remains_review_required(
    tmp_path: Path,
) -> None:
    proposal_path = _proposal(tmp_path)
    observations_path = _observations(tmp_path, proposal_path, items=[])

    report = _build(tmp_path, observations_path)

    assert report["report_status"] == "review_required"
    assert report["reviewed_observation_count"] == 0
    assert report["false_authority_count"] == 0
    assert report["execution_research_ready"] is False
    assert "Review one real formatter policy proposal" in report["next_human_action"]


def test_formatter_proposal_observation_cli_emits_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    proposal_path = _proposal(tmp_path)
    observations_path = _observations(tmp_path, proposal_path)

    rc = observation.main(
        [
            "--observations",
            str(observations_path),
            "--contract-json",
            str(CONTRACT.resolve()),
            "--root",
            str(tmp_path),
            "--out-dir",
            str(tmp_path / "cli-out"),
            "--current-head-sha",
            "b" * 40,
            "--format",
            "json",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["reviewed_observation_count"] == 1
    assert printed["branch_execution_lane_active"] is False
