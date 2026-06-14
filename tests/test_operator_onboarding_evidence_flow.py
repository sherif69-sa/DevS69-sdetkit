from __future__ import annotations

import json
from pathlib import Path

from sdetkit.operator_onboarding_evidence_flow import (
    SCHEMA_VERSION,
    build_operator_onboarding_evidence_flow,
    main,
    render_operator_onboarding_evidence_markdown,
    write_operator_onboarding_evidence_flow,
)


def _seed_operator_repo(root: Path) -> None:
    (root / "src/sdetkit").mkdir(parents=True)
    (root / "scripts").mkdir()
    (root / "docs").mkdir()

    (root / "Makefile").write_text(
        """
operator-onramp: upgrade-next onboarding-next first-proof-dashboard
	@echo "operator-onramp completed"

operator-onramp-dry-run:
	@echo "DRY RUN: make onboarding-next"

operator-onramp-verify: first-proof first-proof-health-score first-proof-verify first-proof-freshness doctor-remediate onboarding-next first-proof-dashboard first-proof-ops-bundle first-proof-ops-bundle-contract first-proof-ops-bundle-trend first-proof-execution-report first-proof-schema-contract first-proof-execution-contract first-proof-followup-ready
	@echo "operator-onramp-verify completed"

operator-onboarding-wizard:
	python scripts/operator_onboarding_wizard.py --format json

onboarding-next:
	python scripts/operator_onboarding_next.py --summary build/first-proof/first-proof-summary.json --out-json build/onboarding-next.json --out-md build/onboarding-next.md --format json
""".lstrip(),
        encoding="utf-8",
    )
    (root / "src/sdetkit/operator_evidence_loop.py").write_text(
        'SCHEMA_VERSION = "sdetkit.operator.evidence_loop.v1"\n',
        encoding="utf-8",
    )
    (root / "src/sdetkit/operator_brief.py").write_text(
        'SCHEMA_VERSION = "sdetkit.operator_brief.v1"\n',
        encoding="utf-8",
    )
    (root / "scripts/operator_onboarding_wizard.py").write_text(
        '"""operator-onboarding wizard."""\n',
        encoding="utf-8",
    )
    (root / "scripts/operator_onboarding_next.py").write_text(
        '"""onboarding-next planner."""\n',
        encoding="utf-8",
    )
    (root / "docs/operator-evidence-review-guide.md").write_text(
        "# Operator evidence review guide\n",
        encoding="utf-8",
    )
    (root / "docs/operator-onboarding-7-day.md").write_text(
        "# Operator onboarding 7-day plan\n",
        encoding="utf-8",
    )


def test_operator_onboarding_evidence_flow_reports_existing_surfaces(tmp_path: Path) -> None:
    _seed_operator_repo(tmp_path)

    payload = build_operator_onboarding_evidence_flow(tmp_path)

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["status"] == "ready_for_operator_review"
    assert payload["reporting_only"] is True
    assert payload["review_first"] is True
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_claim"] is False
    assert payload["next_allowed_action"] == "human_operator_review"

    assert payload["summary"]["present_surface_count"] == 8
    assert payload["summary"]["missing_surface_count"] == 0
    assert payload["summary"]["flow_step_count"] == 7

    boundary = payload["authority_boundary"]
    assert boundary["automation_allowed"] is False
    assert boundary["patch_application_allowed"] is False
    assert boundary["merge_authorized"] is False
    assert boundary["security_dismissal_allowed"] is False
    assert boundary["semantic_equivalence_claim"] is False
    assert boundary["semantic_equivalence_proven"] is False

    surface_ids = {surface["id"] for surface in payload["surfaces"]}
    assert "operator_onramp" in surface_ids
    assert "operator_onboarding_wizard" in surface_ids
    assert "onboarding_next" in surface_ids
    assert "operator_evidence_loop" in surface_ids
    assert "operator_brief" in surface_ids

    step_ids = [step["id"] for step in payload["flow_steps"]]
    assert step_ids[0] == "dry_run_onramp"
    assert "build_operator_evidence_loop" in step_ids
    assert "automatic_merge" in payload["blocked_actions"]


def test_operator_onboarding_evidence_flow_markdown_is_reporting_only(tmp_path: Path) -> None:
    _seed_operator_repo(tmp_path)

    payload = build_operator_onboarding_evidence_flow(tmp_path)
    markdown = render_operator_onboarding_evidence_markdown(payload)

    assert "# Operator onboarding evidence flow" in markdown
    assert "ready_for_operator_review" in markdown
    assert "make operator-onramp-dry-run" in markdown
    assert "make operator-onramp-verify" in markdown
    assert "automation_allowed: `false`" in markdown
    assert "patch_application_allowed: `false`" in markdown
    assert "merge_authorized: `false`" in markdown
    assert "semantic_equivalence_claim: `false`" in markdown
    assert "does not authorize remediation" in markdown


def test_write_operator_onboarding_evidence_flow_outputs_json_and_markdown(tmp_path: Path) -> None:
    _seed_operator_repo(tmp_path)
    out_json = tmp_path / "build/operator-flow/flow.json"
    out_md = tmp_path / "build/operator-flow/flow.md"

    payload = write_operator_onboarding_evidence_flow(tmp_path, out_json, out_md)

    assert out_json.is_file()
    assert out_md.is_file()
    loaded = json.loads(out_json.read_text(encoding="utf-8"))
    assert loaded["schema_version"] == payload["schema_version"]
    assert "Operator onboarding evidence flow" in out_md.read_text(encoding="utf-8")


def test_operator_onboarding_evidence_flow_cli(tmp_path: Path, capsys) -> None:
    _seed_operator_repo(tmp_path)

    rc = main(
        [
            "--root",
            str(tmp_path),
            "--out-json",
            str(tmp_path / "flow.json"),
            "--out-md",
            str(tmp_path / "flow.md"),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    output = json.loads(capsys.readouterr().out)
    assert output["schema_version"] == SCHEMA_VERSION
    assert output["status"] == "ready_for_operator_review"
