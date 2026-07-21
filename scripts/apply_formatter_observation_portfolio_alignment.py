from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected one marker in {path}, found {count}: {old[:80]!r}")
    target.write_text(text.replace(old, new), encoding="utf-8")


MODULE = "src/sdetkit/product_maturity_radar_portfolio.py"

replace_once(
    MODULE,
    "from .adoption_product_kpi_model import REPORT_SCHEMA as KPI_REPORT_SCHEMA\n"
    "from .product_maturity_radar import SCHEMA_VERSION as RADAR_SCHEMA\n",
    "from .adoption_product_kpi_model import REPORT_SCHEMA as KPI_REPORT_SCHEMA\n"
    "from .formatter_policy_proposal_observation import SCHEMA_VERSION as OBSERVATION_SCHEMA\n"
    "from .product_maturity_radar import SCHEMA_VERSION as RADAR_SCHEMA\n",
)
replace_once(
    MODULE,
    'DEFAULT_KPI_REPORT = "build/sdetkit/adoption-product-kpi-report.json"\n',
    'DEFAULT_KPI_REPORT = "build/sdetkit/adoption-product-kpi-report.json"\n'
    'DEFAULT_OBSERVATION_REPORT = (\n'
    '    "build/formatter-policy-proposal-observation/"\n'
    '    "formatter-policy-proposal-observation.json"\n'
    ')\n',
)
replace_once(
    MODULE,
    'REQUIRED_CAPABILITIES = (\n'
    '    "reviewed_repository_kpi_evidence",\n'
    '    "product_maturity_kpi_portfolio_projection",\n'
    ')\n'
    'ACTIVE_ROADMAP_GAP = "formatter_policy_proposal_observation"\n',
    'REQUIRED_CAPABILITIES = (\n'
    '    "reviewed_repository_kpi_evidence",\n'
    '    "product_maturity_kpi_portfolio_projection",\n'
    '    "formatter_policy_proposal_observation",\n'
    ')\n'
    'ACTIVE_ROADMAP_GAP = "formatter_policy_proposal_reviewed_evidence"\n',
)
replace_once(
    MODULE,
    "    kpi_path: Path,\n    matrix_path: Path,\n",
    "    kpi_path: Path,\n    observation_path: Path,\n    matrix_path: Path,\n",
)
replace_once(
    MODULE,
    '        "kpi_report_json": kpi_path.read_bytes(),\n'
    '        "capability_matrix_json": matrix_path.read_bytes(),\n',
    '        "kpi_report_json": kpi_path.read_bytes(),\n'
    '        "proposal_observation_json": observation_path.read_bytes(),\n'
    '        "capability_matrix_json": matrix_path.read_bytes(),\n',
)
replace_once(
    MODULE,
    '        "kpi_report_sha256": hashlib.sha256(inputs["kpi_report_json"]).hexdigest(),\n'
    '        "capability_matrix_path": _display(root, matrix_path),\n',
    '        "kpi_report_sha256": hashlib.sha256(inputs["kpi_report_json"]).hexdigest(),\n'
    '        "proposal_observation_path": _display(root, observation_path),\n'
    '        "proposal_observation_sha256": hashlib.sha256(\n'
    '            inputs["proposal_observation_json"]\n'
    '        ).hexdigest(),\n'
    '        "capability_matrix_path": _display(root, matrix_path),\n',
)

summary_function = '''\n\ndef _proposal_observation_summary(payload: Mapping[str, Any]) -> dict[str, Any]:\n    decision_counts = payload.get("decision_counts")\n    if not isinstance(decision_counts, Mapping):\n        raise ValueError("proposal observation report requires decision_counts")\n    metrics = payload.get("metrics")\n    if not isinstance(metrics, list):\n        raise ValueError("proposal observation report metrics must be a list")\n\n    reviewed_count = int(payload.get("reviewed_observation_count") or 0)\n    normalized_decisions = {\n        str(key): int(value) for key, value in sorted(decision_counts.items())\n    }\n    reasons: list[str] = []\n    if sum(normalized_decisions.values()) != reviewed_count:\n        reasons.append("proposal_observation_decision_count_mismatch")\n    false_authority_count = int(payload.get("false_authority_count") or 0)\n    if false_authority_count != 0:\n        reasons.append("proposal_observation_false_authority")\n    for field in (\n        "execution_research_ready",\n        "branch_execution_lane_active",\n        "broader_maturity_claim_allowed",\n        "observations_authorize_current_action",\n    ):\n        if payload.get(field) is not False:\n            reasons.append(f"proposal_observation_{field}")\n\n    failed_metric_ids = payload.get("failed_metric_ids")\n    if not isinstance(failed_metric_ids, list):\n        raise ValueError("proposal observation report requires failed_metric_ids")\n    normalized_metrics: list[dict[str, Any]] = []\n    for raw in metrics:\n        if not isinstance(raw, Mapping):\n            raise ValueError("proposal observation metrics must contain objects")\n        metric_id = str(raw.get("metric_id") or "").strip()\n        if not metric_id:\n            raise ValueError("proposal observation metrics require ids")\n        normalized_metrics.append(\n            {\n                "metric_id": metric_id,\n                "reviewed_pass_observations": int(\n                    raw.get("reviewed_pass_observations") or 0\n                ),\n                "reviewed_fail_observations": int(\n                    raw.get("reviewed_fail_observations") or 0\n                ),\n                "reviewed_not_applicable_observations": int(\n                    raw.get("reviewed_not_applicable_observations") or 0\n                ),\n                "reviewed_applicable_observations": int(\n                    raw.get("reviewed_applicable_observations") or 0\n                ),\n                "pass_rate": raw.get("pass_rate"),\n            }\n        )\n\n    return {\n        "status": "valid" if not reasons else "invalid",\n        "reasons": sorted(set(reasons)),\n        "reviewed_observation_count": reviewed_count,\n        "decision_counts": normalized_decisions,\n        "metric_count": len(normalized_metrics),\n        "metrics": sorted(normalized_metrics, key=lambda item: item["metric_id"]),\n        "failed_metric_ids": sorted(str(item) for item in failed_metric_ids),\n        "false_authority_count": false_authority_count,\n        "next_human_action": str(payload.get("next_human_action") or "").strip(),\n        "execution_research_ready": False,\n        "branch_execution_lane_active": False,\n        "broader_maturity_claim_allowed": False,\n        "observations_authorize_current_action": False,\n    }\n'''
replace_once(
    MODULE,
    "\n\ndef _capability_matrix_summary(payload: Mapping[str, Any]) -> dict[str, Any]:\n",
    summary_function + "\n\ndef _capability_matrix_summary(payload: Mapping[str, Any]) -> dict[str, Any]:\n",
)
replace_once(
    MODULE,
    '    if ACTIVE_ROADMAP_GAP not in active_gap_ids:\n'
    '        reasons.append("active_guarded_remediation_gap_missing")\n',
    '    if ACTIVE_ROADMAP_GAP not in active_gap_ids:\n'
    '        reasons.append("active_proposal_observation_evidence_gap_missing")\n'
    '    if "formatter_policy_proposal_observation" in active_gap_ids:\n'
    '        reasons.append("implemented_observation_capability_still_active_as_gap")\n',
)
replace_once(
    MODULE,
    '        "formatter_policy_proposal_observation_active": ACTIVE_ROADMAP_GAP in active_gap_ids,\n'
    '        "real_repository_kpi_gap_active": "real_repository_kpi_evidence" in active_gap_ids,\n',
    '        "formatter_policy_proposal_observation_active": (\n'
    '            "formatter_policy_proposal_observation" in active_gap_ids\n'
    '        ),\n'
    '        "formatter_policy_proposal_reviewed_evidence_active": (\n'
    '            ACTIVE_ROADMAP_GAP in active_gap_ids\n'
    '        ),\n'
    '        "real_repository_kpi_gap_active": "real_repository_kpi_evidence" in active_gap_ids,\n',
)
replace_once(
    MODULE,
    '        "two reviewed observations",\n'
    '        f"`{ACTIVE_ROADMAP_GAP}`",\n',
    '        "two reviewed observations",\n'
    '        "formatter-policy-proposal-observation.json",\n'
    '        f"`{ACTIVE_ROADMAP_GAP}`",\n',
)
replace_once(
    MODULE,
    '        "metrics_without_applicable_denominator",\n'
    '        f"`{ACTIVE_ROADMAP_GAP}`",\n',
    '        "metrics_without_applicable_denominator",\n'
    '        "formatter_policy_proposal_observation",\n'
    '        f"`{ACTIVE_ROADMAP_GAP}`",\n',
)
replace_once(
    MODULE,
    "    kpi_report_json: str | Path = DEFAULT_KPI_REPORT,\n"
    "    capability_matrix_json: str | Path = DEFAULT_CAPABILITY_MATRIX,\n",
    "    kpi_report_json: str | Path = DEFAULT_KPI_REPORT,\n"
    "    proposal_observation_report_json: str | Path = DEFAULT_OBSERVATION_REPORT,\n"
    "    capability_matrix_json: str | Path = DEFAULT_CAPABILITY_MATRIX,\n",
)
replace_once(
    MODULE,
    "    kpi_path = Path(kpi_report_json).resolve()\n"
    "    matrix_path = Path(capability_matrix_json).resolve()\n",
    "    kpi_path = Path(kpi_report_json).resolve()\n"
    "    observation_path = Path(proposal_observation_report_json).resolve()\n"
    "    matrix_path = Path(capability_matrix_json).resolve()\n",
)
replace_once(
    MODULE,
    '    kpi = _load_object(kpi_path, label="adoption product KPI report")\n'
    '    matrix = _load_object(matrix_path, label="platform capability matrix")\n',
    '    kpi = _load_object(kpi_path, label="adoption product KPI report")\n'
    '    observation = _load_object(\n'
    '        observation_path, label="formatter policy proposal observation report"\n'
    '    )\n'
    '    matrix = _load_object(matrix_path, label="platform capability matrix")\n',
)
replace_once(
    MODULE,
    '    kpi_summary = _metric_summary(kpi)\n'
    '    matrix_summary = _capability_matrix_summary(matrix)\n',
    '    observation_source = _source_report_record(\n'
    '        observation,\n'
    '        source_id="formatter_policy_proposal_observation",\n'
    '        expected_schema=OBSERVATION_SCHEMA,\n'
    '        current_head_sha=head,\n'
    '        authority_fields=AUTHORITY_FIELDS,\n'
    '    )\n'
    '    kpi_summary = _metric_summary(kpi)\n'
    '    observation_summary = _proposal_observation_summary(observation)\n'
    '    matrix_summary = _capability_matrix_summary(matrix)\n',
)
replace_once(
    MODULE,
    "    for source in (radar_source, kpi_source):\n",
    "    for source in (radar_source, kpi_source, observation_source):\n",
)
replace_once(
    MODULE,
    '    if matrix_summary["status"] != "aligned":\n'
    '        blocked_reasons.extend(matrix_summary["reasons"])\n',
    '    if observation_summary["status"] != "valid":\n'
    '        blocked_reasons.extend(observation_summary["reasons"])\n'
    '    if matrix_summary["status"] != "aligned":\n'
    '        blocked_reasons.extend(matrix_summary["reasons"])\n',
)
replace_once(
    MODULE,
    '        if kpi_summary["unavailable_metric_count"]\n'
    '        else "reviewed_evidence_available"\n',
    '        if (\n'
    '            kpi_summary["unavailable_metric_count"]\n'
    '            or observation_summary["reviewed_observation_count"] == 0\n'
    '        )\n'
    '        else "reviewed_evidence_available"\n',
)
replace_once(
    MODULE,
    '    evidence_next_action = (\n'
    '        "Collect reviewed observations for: " + ", ".join(unavailable)\n'
    '        if unavailable\n'
    '        else "Continue collecting reviewed external-repository observations before broader claims."\n'
    '    )\n',
    '    evidence_next_action = (\n'
    '        "Collect reviewed observations for: " + ", ".join(unavailable)\n'
    '        if unavailable\n'
    '        else observation_summary["next_human_action"]\n'
    '        or "Review one real formatter policy proposal and retain its exact source artifact."\n'
    '    )\n',
)
replace_once(
    MODULE,
    "        kpi_path=kpi_path,\n        matrix_path=matrix_path,\n",
    "        kpi_path=kpi_path,\n        observation_path=observation_path,\n        matrix_path=matrix_path,\n",
)
replace_once(
    MODULE,
    '        "reviewed_kpi_evidence": {\n'
    '            "source": kpi_source,\n'
    '            **kpi_summary,\n'
    '        },\n'
    '        "capability_matrix": matrix_summary,\n',
    '        "reviewed_kpi_evidence": {\n'
    '            "source": kpi_source,\n'
    '            **kpi_summary,\n'
    '        },\n'
    '        "formatter_policy_proposal_observation": {\n'
    '            "source": observation_source,\n'
    '            **observation_summary,\n'
    '        },\n'
    '        "capability_matrix": matrix_summary,\n',
)
replace_once(
    MODULE,
    '            "status": "review_required" if unavailable else "reviewed_evidence_available",\n'
    '            "reviewed_observation_count": kpi_summary["reviewed_observation_count"],\n',
    '            "status": (\n'
    '                "review_required"\n'
    '                if unavailable or observation_summary["reviewed_observation_count"] == 0\n'
    '                else "reviewed_evidence_available"\n'
    '            ),\n'
    '            "reviewed_observation_count": kpi_summary["reviewed_observation_count"],\n'
    '            "proposal_reviewed_observation_count": observation_summary[\n'
    '                "reviewed_observation_count"\n'
    '            ],\n'
    '            "proposal_false_authority_count": observation_summary[\n'
    '                "false_authority_count"\n'
    '            ],\n',
)
replace_once(
    MODULE,
    '    operator = payload.get("operator_summary")\n'
    '    operator = operator if isinstance(operator, Mapping) else {}\n'
    '    radar = payload.get("radar_projection")\n',
    '    operator = payload.get("operator_summary")\n'
    '    operator = operator if isinstance(operator, Mapping) else {}\n'
    '    observation = payload.get("formatter_policy_proposal_observation")\n'
    '    observation = observation if isinstance(observation, Mapping) else {}\n'
    '    radar = payload.get("radar_projection")\n',
)
replace_once(
    MODULE,
    '        f"- unavailable_metric_count: `{kpi.get(\'unavailable_metric_count\', 0)}`",\n'
    '        "- reporting_only: true",\n',
    '        f"- unavailable_metric_count: `{kpi.get(\'unavailable_metric_count\', 0)}`",\n'
    '        "- proposal_reviewed_observation_count: "\n'
    '        f"`{observation.get(\'reviewed_observation_count\', 0)}`",\n'
    '        "- proposal_false_authority_count: "\n'
    '        f"`{observation.get(\'false_authority_count\', 0)}`",\n'
    '        "- reporting_only: true",\n',
)
replace_once(
    MODULE,
    '            "## Portfolio alignment",\n'
    '            "",\n',
    '            "## Formatter proposal observation",\n'
    '            "",\n'
    '            "- source_status: "\n'
    '            f"`{observation.get(\'source\', {}).get(\'status\', \'unknown\')}`",\n'
    '            "- reviewed_observation_count: "\n'
    '            f"`{observation.get(\'reviewed_observation_count\', 0)}`",\n'
    '            "- failed_metric_ids: "\n'
    '            f"`{\',\'.join(observation.get(\'failed_metric_ids\', [])) or \'none\'}`",\n'
    '            "",\n'
    '            "## Portfolio alignment",\n'
    '            "",\n',
)
replace_once(
    MODULE,
    '        "reviewed_kpi_evidence",\n'
    '        "capability_matrix",\n',
    '        "reviewed_kpi_evidence",\n'
    '        "formatter_policy_proposal_observation",\n'
    '        "capability_matrix",\n',
)
replace_once(
    MODULE,
    '    parser.add_argument("--kpi-report-json", default=DEFAULT_KPI_REPORT)\n'
    '    parser.add_argument("--capability-matrix-json", default=DEFAULT_CAPABILITY_MATRIX)\n',
    '    parser.add_argument("--kpi-report-json", default=DEFAULT_KPI_REPORT)\n'
    '    parser.add_argument(\n'
    '        "--proposal-observation-report-json", default=DEFAULT_OBSERVATION_REPORT\n'
    '    )\n'
    '    parser.add_argument("--capability-matrix-json", default=DEFAULT_CAPABILITY_MATRIX)\n',
)
replace_once(
    MODULE,
    '        "kpi_report_json": ns.kpi_report_json,\n'
    '        "capability_matrix_json": ns.capability_matrix_json,\n',
    '        "kpi_report_json": ns.kpi_report_json,\n'
    '        "proposal_observation_report_json": ns.proposal_observation_report_json,\n'
    '        "capability_matrix_json": ns.capability_matrix_json,\n',
)

TEST = "tests/test_product_maturity_radar_portfolio.py"
replace_once(
    TEST,
    "from sdetkit.adoption_product_kpi_model import REPORT_SCHEMA as KPI_REPORT_SCHEMA\n"
    "from sdetkit.product_maturity_radar import SCHEMA_VERSION as RADAR_SCHEMA\n",
    "from sdetkit.adoption_product_kpi_model import REPORT_SCHEMA as KPI_REPORT_SCHEMA\n"
    "from sdetkit.formatter_policy_proposal_observation import (\n"
    "    SCHEMA_VERSION as OBSERVATION_SCHEMA,\n"
    ")\n"
    "from sdetkit.product_maturity_radar import SCHEMA_VERSION as RADAR_SCHEMA\n",
)
replace_once(
    TEST,
    "NOT_APPLICABLE_ONCE = {\n"
    '    "discovery_precision",\n'
    '    "first_failure_extraction_precision",\n'
    '    "workspace_ownership_precision",\n'
    "}\n",
    "NOT_APPLICABLE_ONCE = {\n"
    '    "discovery_precision",\n'
    '    "first_failure_extraction_precision",\n'
    '    "workspace_ownership_precision",\n'
    "}\n"
    "OBSERVATION_METRIC_IDS = (\n"
    '    "exact_evidence_binding",\n'
    '    "proposal_scope_clarity",\n'
    '    "proof_plan_actionability",\n'
    '    "rollback_clarity",\n'
    '    "authority_boundary_preservation",\n'
    '    "operator_usefulness",\n'
    ")\n",
)
observation_fixture = '''\n\ndef _observation_payload() -> dict:\n    return {\n        "schema_version": OBSERVATION_SCHEMA,\n        "report_status": "review_required",\n        "reviewed_observation_count": 0,\n        "decision_counts": {\n            "accept": 0,\n            "reject": 0,\n            "defer": 0,\n            "request_more_evidence": 0,\n        },\n        "metrics": [\n            {\n                "metric_id": metric_id,\n                "reviewed_pass_observations": 0,\n                "reviewed_fail_observations": 0,\n                "reviewed_not_applicable_observations": 0,\n                "reviewed_applicable_observations": 0,\n                "pass_rate": None,\n            }\n            for metric_id in OBSERVATION_METRIC_IDS\n        ],\n        "failed_metric_ids": [],\n        "false_authority_count": 0,\n        "next_human_action": (\n            "Review one real formatter policy proposal and retain its exact source artifact."\n        ),\n        "execution_research_ready": False,\n        "branch_execution_lane_active": False,\n        "broader_maturity_claim_allowed": False,\n        "observations_authorize_current_action": False,\n        "current_head_sha": HEAD,\n        "input_provenance": {\n            "input_digest": "3" * 64,\n            "generator_schema_version": OBSERVATION_SCHEMA,\n            "current_head_sha": HEAD,\n        },\n        "authority_boundary": _authority(),\n        **_authority(),\n    }\n'''
replace_once(TEST, "\n\ndef _capability_matrix(*, keep_completed_gap: bool = False) -> dict:\n", observation_fixture + "\n\ndef _capability_matrix(*, keep_completed_gap: bool = False) -> dict:\n")
replace_once(
    TEST,
    '            "gap_id": "formatter_policy_proposal_observation",\n'
    '            "priority": "P2",\n'
    '            "review_first": True,\n'
    '            "title": "Evaluate one narrow safe-remediation policy promotion",\n'
    '            "exit_criteria": "Prove benchmark, verifier, trajectory, and false-authority checks.",\n'
    '            "suggested_owner_files": ["src/sdetkit/safety_gate.py", "tests"],\n',
    '            "gap_id": "formatter_policy_proposal_reviewed_evidence",\n'
    '            "priority": "P2",\n'
    '            "review_first": True,\n'
    '            "title": "Retain one real reviewed formatter proposal observation",\n'
    '            "exit_criteria": "Retain one digest-bound reviewed proposal with zero false authority.",\n'
    '            "suggested_owner_files": [\n'
    '                "docs/evidence/formatter-policy-proposal/reviewed-observations.v1.json",\n'
    '                "docs/formatter-policy-proposal-observation.md",\n'
    '            ],\n',
)
replace_once(
    TEST,
    '            {\n'
    '                "capability_id": "product_maturity_kpi_portfolio_projection",\n'
    '                "status": "implemented_and_tested",\n'
    '                "authority": "reporting_only",\n'
    '                "title": "KPI portfolio projection",\n'
    '                "owner_files": ["src/sdetkit/product_maturity_radar_portfolio.py"],\n'
    '                "proof_tests": ["tests/test_product_maturity_radar_portfolio.py"],\n'
    '            },\n',
    '            {\n'
    '                "capability_id": "product_maturity_kpi_portfolio_projection",\n'
    '                "status": "implemented_and_tested",\n'
    '                "authority": "reporting_only",\n'
    '                "title": "KPI portfolio projection",\n'
    '                "owner_files": ["src/sdetkit/product_maturity_radar_portfolio.py"],\n'
    '                "proof_tests": ["tests/test_product_maturity_radar_portfolio.py"],\n'
    '            },\n'
    '            {\n'
    '                "capability_id": "formatter_policy_proposal_observation",\n'
    '                "status": "implemented_and_tested",\n'
    '                "authority": "reporting_only",\n'
    '                "title": "Formatter proposal observation",\n'
    '                "owner_files": [\n'
    '                    "src/sdetkit/formatter_policy_proposal_observation.py"\n'
    '                ],\n'
    '                "proof_tests": [\n'
    '                    "tests/test_formatter_policy_proposal_observation.py"\n'
    '                ],\n'
    '            },\n',
)
replace_once(
    TEST,
    '    kpi = _write_json(tmp_path / "build" / "kpi.json", _kpi_payload())\n'
    '    matrix = _write_json(\n',
    '    kpi = _write_json(tmp_path / "build" / "kpi.json", _kpi_payload())\n'
    '    observation = _write_json(\n'
    '        tmp_path / "build" / "proposal-observation.json", _observation_payload()\n'
    '    )\n'
    '    matrix = _write_json(\n',
)
replace_once(
    TEST,
    '        "Next: `formatter_policy_proposal_observation`.\\n",\n',
    '        "Artifact: formatter-policy-proposal-observation.json\\n"\n'
    '        "Next: `formatter_policy_proposal_reviewed_evidence`.\\n",\n',
)
replace_once(
    TEST,
    '        "metrics_without_applicable_denominator\\n"\n'
    '        "`formatter_policy_proposal_observation`\\n",\n',
    '        "metrics_without_applicable_denominator\\n"\n'
    '        "formatter_policy_proposal_observation\\n"\n'
    '        "`formatter_policy_proposal_reviewed_evidence`\\n",\n',
)
replace_once(
    TEST,
    '        "kpi_report_json": kpi,\n'
    '        "capability_matrix_json": matrix,\n',
    '        "kpi_report_json": kpi,\n'
    '        "proposal_observation_report_json": observation,\n'
    '        "capability_matrix_json": matrix,\n',
)
replace_once(
    TEST,
    '    assert payload["report_status"] == "reviewed_evidence_available"\n',
    '    assert payload["report_status"] == "review_required"\n',
)
replace_once(
    TEST,
    '    assert payload["reviewed_kpi_evidence"]["outcome_totals"]["not_applicable"] == 3\n'
    '    assert payload["reviewed_kpi_evidence"]["broader_maturity_claim_allowed"] is False\n',
    '    assert payload["reviewed_kpi_evidence"]["outcome_totals"]["not_applicable"] == 3\n'
    '    assert payload["reviewed_kpi_evidence"]["broader_maturity_claim_allowed"] is False\n'
    '    observation = payload["formatter_policy_proposal_observation"]\n'
    '    assert observation["source"]["status"] == "fresh"\n'
    '    assert observation["reviewed_observation_count"] == 0\n'
    '    assert observation["false_authority_count"] == 0\n'
    '    assert observation["execution_research_ready"] is False\n',
)
replace_once(
    TEST,
    '    assert payload["capability_matrix"]["formatter_policy_proposal_observation_active"] is True\n',
    '    assert (\n'
    '        payload["capability_matrix"][\n'
    '            "formatter_policy_proposal_reviewed_evidence_active"\n'
    '        ]\n'
    '        is True\n'
    '    )\n'
    '    assert payload["capability_matrix"]["formatter_policy_proposal_observation_active"] is False\n',
)
replace_once(
    TEST,
    '    assert "Continue collecting reviewed" in payload["operator_summary"]["evidence_next_action"]\n'
    '    assert (\n'
    '        payload["operator_summary"]["roadmap_next_slice"] == "formatter_policy_proposal_observation"\n'
    '    )\n',
    '    assert "Review one real formatter policy proposal" in payload["operator_summary"][\n'
    '        "evidence_next_action"\n'
    '    ]\n'
    '    assert payload["operator_summary"]["proposal_reviewed_observation_count"] == 0\n'
    '    assert payload["operator_summary"]["proposal_false_authority_count"] == 0\n'
    '    assert (\n'
    '        payload["operator_summary"]["roadmap_next_slice"]\n'
    '        == "formatter_policy_proposal_reviewed_evidence"\n'
    '    )\n',
)

print("portfolio_alignment=applied")
