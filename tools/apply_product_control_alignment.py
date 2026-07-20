from __future__ import annotations

import ast
import json
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one exact target, found {count}")
    target.write_text(text.replace(old, new), encoding="utf-8")
    print(f"patched_exact={path}")


def replace_section(path: str, start_marker: str, end_marker: str, replacement: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    start = text.find(start_marker)
    if start < 0:
        raise SystemExit(f"{path}: missing start marker {start_marker!r}")
    end = text.find(end_marker, start + len(start_marker))
    if end < 0:
        raise SystemExit(f"{path}: missing end marker {end_marker!r}")
    target.write_text(text[:start] + replacement + text[end:], encoding="utf-8")
    print(f"patched_section={path}:{start_marker.strip()}")


def patch_portfolio_source() -> None:
    path = "src/sdetkit/product_maturity_radar_portfolio.py"
    replace_once(
        path,
        '''REQUIRED_CAPABILITIES = (
    "reviewed_repository_kpi_evidence",
    "product_maturity_kpi_portfolio_projection",
)
''',
        '''REQUIRED_CAPABILITIES = (
    "reviewed_repository_kpi_evidence",
    "product_maturity_kpi_portfolio_projection",
)
ACTIVE_ROADMAP_GAP = "guarded_remediation_promotion"
''',
    )
    replace_section(
        path,
        "def _capability_matrix_summary(payload: Mapping[str, Any]) -> dict[str, Any]:\n",
        "def _documentation_summary(roadmap_text: str, operator_text: str) -> dict[str, Any]:\n",
        '''def _capability_matrix_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    if payload.get("schema_version") != MATRIX_SCHEMA:
        reasons.append("capability_matrix_schema_mismatch")
    authority = payload.get("authority_boundary")
    if not isinstance(authority, Mapping) or any(
        authority.get(field) is not False for field in AUTHORITY_FIELDS
    ):
        reasons.append("capability_matrix_authority_expansion")

    raw_capabilities = payload.get("capabilities")
    raw_capabilities = raw_capabilities if isinstance(raw_capabilities, list) else []
    by_id = {
        str(item.get("capability_id")): item
        for item in raw_capabilities
        if isinstance(item, Mapping) and item.get("capability_id")
    }
    missing = [
        capability_id for capability_id in REQUIRED_CAPABILITIES if capability_id not in by_id
    ]
    if missing:
        reasons.append("required_capabilities_missing")
    for capability_id in REQUIRED_CAPABILITIES:
        item = by_id.get(capability_id)
        if item is not None and item.get("status") != "implemented_and_tested":
            reasons.append(f"capability_not_implemented:{capability_id}")

    raw_gaps = payload.get("active_repository_gaps")
    raw_gaps = raw_gaps if isinstance(raw_gaps, list) else []
    active_gap_ids = {
        str(item.get("gap_id"))
        for item in raw_gaps
        if isinstance(item, Mapping) and item.get("gap_id")
    }
    if "real_repository_kpi_evidence" in active_gap_ids:
        reasons.append("completed_kpi_gap_still_active")
    if ACTIVE_ROADMAP_GAP not in active_gap_ids:
        reasons.append("active_guarded_remediation_gap_missing")

    return {
        "status": "aligned" if not reasons else "misaligned",
        "reasons": sorted(set(reasons)),
        "required_capabilities": list(REQUIRED_CAPABILITIES),
        "present_capabilities": sorted(
            capability_id for capability_id in REQUIRED_CAPABILITIES if capability_id in by_id
        ),
        "active_repository_gaps": sorted(active_gap_ids),
        "guarded_remediation_promotion_active": ACTIVE_ROADMAP_GAP in active_gap_ids,
        "real_repository_kpi_gap_active": "real_repository_kpi_evidence" in active_gap_ids,
        "authority_valid": "capability_matrix_authority_expansion" not in reasons,
    }


''',
    )
    replace_section(
        path,
        "def _documentation_summary(roadmap_text: str, operator_text: str) -> dict[str, Any]:\n",
        "def build_portfolio_report(\n",
        '''def _documentation_summary(roadmap_text: str, operator_text: str) -> dict[str, Any]:
    roadmap_tokens = (
        "adoption-product-kpi-report.json",
        "reviewed real-repository KPI baseline is complete",
        "two reviewed observations",
        f"`{ACTIVE_ROADMAP_GAP}`",
    )
    operator_tokens = (
        "product-maturity-radar-portfolio.json",
        "reviewed_observation_count",
        "metrics_without_applicable_denominator",
        f"`{ACTIVE_ROADMAP_GAP}`",
    )
    missing_roadmap = [token for token in roadmap_tokens if token not in roadmap_text]
    missing_operator = [token for token in operator_tokens if token not in operator_text]
    return {
        "status": "aligned" if not missing_roadmap and not missing_operator else "misaligned",
        "missing_roadmap_markers": missing_roadmap,
        "missing_operator_markers": missing_operator,
        "roadmap_next_slice": ACTIVE_ROADMAP_GAP,
        "operator_report_documented": not missing_operator,
    }


''',
    )


def patch_roadmap() -> None:
    path = "docs/roadmap/product-roadmap.md"
    replace_once(
        path,
        "| Learning | TrajectoryStore, RepoMemory, benchmark, patterns, and one reviewed external-repository KPI observation exist. | Expand reviewed denominators without broad maturity claims. |",
        "| Learning | TrajectoryStore, RepoMemory, benchmark, patterns, and two reviewed source-backed KPI observations exist. | Continue reviewed evidence collection without broad maturity claims while advancing guarded remediation research. |",
    )
    replace_once(
        path,
        "| Reviewed KPI baseline | One source-backed real-repository observation produces five measured metrics and two explicit unavailable metrics in `adoption-product-kpi-report.json`. |",
        "| Reviewed KPI baseline | Two source-backed reviewed observations produce eleven reviewed pass outcomes, three explicit `not_applicable` outcomes, seven measured metrics, and zero unavailable metrics in `adoption-product-kpi-report.json`. |",
    )
    replace_once(
        path,
        '''| 1 | **Product evidence: expand reviewed KPI denominators** | Exercise failure extraction and workspace ownership without hiding unavailable evidence. | Additional reviewed observations produce applicable denominators while preserving exact source provenance and denied authority. |
| 2 | **Safety research: one narrow remediation promotion** | Evaluate a reversible PR-owned mechanical family. | Benchmark, independent verifier, rollback, trajectory, and zero unsafe false-authority decisions are proven before policy changes. |''',
        '''| 1 | **Product control: `guarded_remediation_promotion`** | Define the versioned, review-first remediation-research contract for one reversible PR-owned mechanical family. | The contract covers no-op, oracle, unsafe-patch, out-of-scope, ambiguous, rollback, reviewer, proof, and false-authority evidence without changing SafetyGate policy. |
| 2 | **Candidate benchmark: formatter-only** | Evaluate the first mechanical family without promotion. | Benchmark and verifier evidence prove zero out-of-scope writes, zero test weakening, deterministic rollback, retained artifacts, exact source digests, and explicit false-positive reporting. |''',
    )
    replace_once(
        path,
        '''The first `adoption-product-kpi-report.json` is source-backed, exact-head bound, and contains one reviewed observation. Five metrics have an applicable denominator and pass that reviewed observation. First-failure extraction and workspace ownership remain explicitly unavailable because the observation did not exercise those conditions.

The portfolio projection consumes this verified artifact without becoming a new source of authority. Continue collecting reviewed observations until the missing denominators are exercised; do not infer outcomes or generalize one repository into a broad maturity claim.''',
        '''The current `adoption-product-kpi-report.json` is source-backed, exact-head bound, and contains two reviewed observations. Across the seven contracted metrics it records eleven reviewed pass outcomes and three explicit `not_applicable` outcomes. Every metric now has an applicable reviewed denominator, so `measured_metric_count=7` and `unavailable_metric_count=0`.

The portfolio projection consumes this verified artifact without becoming a new source of authority. Denominator expansion is complete, but two observations still do not support a broad maturity claim. Continue collecting reviewed evidence while the next implementation lane advances to `guarded_remediation_promotion`: a versioned, review-first remediation-research contract with no SafetyGate policy change or patch authority.''',
    )


def patch_operator_guide() -> None:
    path = "docs/operator-reviewed-kpi-portfolio-report.md"
    replace_once(
        path,
        '''The first baseline contains one reviewed observation, five measured metrics, and two unavailable metrics:

```text
first_failure_extraction_precision
workspace_ownership_precision
```

Those two metrics retain `precision=null` because this observation did not exercise a failing CI log or a mixed-workspace ownership decision. They are not converted into passes or authoritative zeroes.''',
        '''The current baseline contains two reviewed observations, seven measured metrics, and zero unavailable metrics. Its reviewed outcomes total:

```text
pass=11
fail=0
unavailable=0
malformed=0
unsupported=0
not_applicable=3
```

All seven metrics now have applicable reviewed denominators. The three `not_applicable` outcomes remain visible because a reviewed observation may legitimately not exercise every metric; they are not converted into passes, failures, or authoritative zeroes.''',
    )
    replace_once(
        path,
        '''The operator summary separates two next actions:

- `evidence_next_action` identifies which reviewed denominators still need observations;
- `roadmap_next_slice` identifies the next implementation lane, currently conservative Azure DevOps proof discovery.

Neither next action authorizes code changes or target-repository execution.''',
        '''The operator summary separates evidence continuity from the active implementation lane:

- `evidence_next_action` continues reviewed observation collection before broader product claims;
- `roadmap_next_slice` identifies the next review-first implementation lane: `guarded_remediation_promotion`.

Neither next action authorizes code changes, patch application, SafetyGate policy promotion, or target-repository execution.''',
    )


def patch_portfolio_tests() -> None:
    path = "tests/test_product_maturity_radar_portfolio.py"
    replace_once(
        path,
        '''UNAVAILABLE = {
    "first_failure_extraction_precision",
    "workspace_ownership_precision",
}
''',
        '''NOT_APPLICABLE_ONCE = {
    "discovery_precision",
    "first_failure_extraction_precision",
    "workspace_ownership_precision",
}
''',
    )
    replace_section(
        path,
        "def _kpi_payload() -> dict:\n",
        "def _capability_matrix(*, keep_completed_gap: bool = False) -> dict:\n",
        '''def _kpi_payload() -> dict:
    metrics = []
    for metric_id in METRIC_IDS:
        not_applicable = metric_id in NOT_APPLICABLE_ONCE
        metrics.append(
            {
                "metric_id": metric_id,
                "status": "measured",
                "precision": 1.0,
                "reviewed_pass_observations": 1 if not_applicable else 2,
                "reviewed_applicable_observations": 1 if not_applicable else 2,
                "outcome_counts": {
                    "pass": 1 if not_applicable else 2,
                    "fail": 0,
                    "unavailable": 0,
                    "malformed": 0,
                    "unsupported": 0,
                    "not_applicable": 1 if not_applicable else 0,
                },
            }
        )
    return {
        "schema_version": KPI_REPORT_SCHEMA,
        "report_status": "reviewed_evidence_available",
        "reviewed_observation_count": 2,
        "metric_count": 7,
        "metrics": metrics,
        "metrics_without_applicable_denominator": [],
        "outcome_totals": {
            "pass": 11,
            "fail": 0,
            "unavailable": 0,
            "malformed": 0,
            "unsupported": 0,
            "not_applicable": 3,
        },
        "current_head_sha": HEAD,
        "input_provenance": {
            "input_digest": "2" * 64,
            "generator_schema_version": KPI_REPORT_SCHEMA,
            "current_head_sha": HEAD,
        },
        "source_relationships": {
            "contract_schema_accepted": True,
            "observations_schema_accepted": True,
            "current_head_bound": True,
        },
        "authority_boundary": _authority(),
        **_authority(),
    }


''',
    )
    replace_section(
        path,
        "def _capability_matrix(*, keep_completed_gap: bool = False) -> dict:\n",
        "def _fixture_paths(tmp_path: Path, *, keep_completed_gap: bool = False) -> dict[str, Path]:\n",
        '''def _capability_matrix(*, keep_completed_gap: bool = False) -> dict:
    gaps = [
        {
            "gap_id": "guarded_remediation_promotion",
            "priority": "P2",
            "review_first": True,
            "title": "Evaluate one narrow safe-remediation policy promotion",
            "exit_criteria": "Prove benchmark, verifier, trajectory, and false-authority checks.",
            "suggested_owner_files": ["src/sdetkit/safety_gate.py", "tests"],
        }
    ]
    if keep_completed_gap:
        gaps.append(
            {
                "gap_id": "real_repository_kpi_evidence",
                "priority": "P1",
                "review_first": True,
                "title": "legacy gap",
                "exit_criteria": "legacy gap",
                "suggested_owner_files": ["src/sdetkit"],
            }
        )
    return {
        "schema_version": "sdetkit.platform_capability_matrix.v1",
        "product_stage": "local_first_reliability_platform",
        "authority_boundary": _authority(),
        "active_repository_gaps": gaps,
        "capabilities": [
            {
                "capability_id": "reviewed_repository_kpi_evidence",
                "status": "implemented_and_tested",
                "authority": "reporting_only",
                "title": "Reviewed KPI evidence",
                "owner_files": ["src/sdetkit/adoption_product_kpi_model.py"],
                "proof_tests": ["tests/test_adoption_product_kpi_model.py"],
            },
            {
                "capability_id": "product_maturity_kpi_portfolio_projection",
                "status": "implemented_and_tested",
                "authority": "reporting_only",
                "title": "KPI portfolio projection",
                "owner_files": ["src/sdetkit/product_maturity_radar_portfolio.py"],
                "proof_tests": ["tests/test_product_maturity_radar_portfolio.py"],
            },
        ],
        "external_or_manual_blockers": [],
        "intentionally_blocked": [],
    }


''',
    )
    replace_section(
        path,
        "def _fixture_paths(tmp_path: Path, *, keep_completed_gap: bool = False) -> dict[str, Path]:\n",
        "def test_portfolio_report_integrates_reviewed_kpi_truth_without_inference(\n",
        '''def _fixture_paths(tmp_path: Path, *, keep_completed_gap: bool = False) -> dict[str, Path]:
    radar = _write_json(tmp_path / "build" / "radar.json", _radar_payload())
    kpi = _write_json(tmp_path / "build" / "kpi.json", _kpi_payload())
    matrix = _write_json(
        tmp_path / "docs" / "contracts" / "matrix.json",
        _capability_matrix(keep_completed_gap=keep_completed_gap),
    )
    roadmap = tmp_path / "docs" / "roadmap.md"
    roadmap.parent.mkdir(parents=True, exist_ok=True)
    roadmap.write_text(
        "The reviewed real-repository KPI baseline is complete.\n"
        "Artifact: adoption-product-kpi-report.json\n"
        "The baseline now contains two reviewed observations.\n"
        "Next: `guarded_remediation_promotion`.\n",
        encoding="utf-8",
    )
    operator = tmp_path / "docs" / "operator.md"
    operator.write_text(
        "product-maturity-radar-portfolio.json\n"
        "reviewed_observation_count\n"
        "metrics_without_applicable_denominator\n"
        "`guarded_remediation_promotion`\n",
        encoding="utf-8",
    )
    return {
        "radar_json": radar,
        "kpi_report_json": kpi,
        "capability_matrix_json": matrix,
        "roadmap_markdown": roadmap,
        "operator_guide_markdown": operator,
    }


''',
    )
    replace_section(
        path,
        "def test_portfolio_report_integrates_reviewed_kpi_truth_without_inference(\n",
        "def test_portfolio_report_blocks_completed_gap_or_authority_expansion(tmp_path: Path) -> None:\n",
        '''def test_portfolio_report_integrates_reviewed_kpi_truth_without_inference(
    tmp_path: Path,
) -> None:
    paths = _fixture_paths(tmp_path)

    payload = build_portfolio_report(root=tmp_path, current_head_sha=HEAD, **paths)

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["portfolio_status"] == "current"
    assert payload["report_status"] == "reviewed_evidence_available"
    assert payload["radar_projection"]["source"]["status"] == "fresh"
    assert payload["reviewed_kpi_evidence"]["source"]["status"] == "fresh"
    assert payload["reviewed_kpi_evidence"]["baseline_status"] == "complete_reviewed_baseline"
    assert payload["reviewed_kpi_evidence"]["reviewed_observation_count"] == 2
    assert payload["reviewed_kpi_evidence"]["measured_metric_count"] == 7
    assert payload["reviewed_kpi_evidence"]["unavailable_metric_count"] == 0
    assert payload["reviewed_kpi_evidence"]["metrics_without_applicable_denominator"] == []
    assert payload["reviewed_kpi_evidence"]["outcome_totals"]["pass"] == 11
    assert payload["reviewed_kpi_evidence"]["outcome_totals"]["not_applicable"] == 3
    assert payload["reviewed_kpi_evidence"]["broader_maturity_claim_allowed"] is False
    assert payload["capability_matrix"]["status"] == "aligned"
    assert payload["capability_matrix"]["guarded_remediation_promotion_active"] is True
    assert payload["portfolio_documentation"]["status"] == "aligned"
    assert "Continue collecting reviewed" in payload["operator_summary"]["evidence_next_action"]
    assert payload["operator_summary"]["roadmap_next_slice"] == "guarded_remediation_promotion"
    assert all(payload[field] is False for field in AUTHORITY_FIELDS)
    assert all(value is False for value in payload["authority_boundary"].values())


''',
    )
    replace_once(
        path,
        '    kpi["reviewed_observation_count"] = 2\n',
        '    kpi["reviewed_observation_count"] = 3\n',
    )


def patch_capability_matrix_test() -> None:
    replace_once(
        "tests/test_platform_capability_matrix.py",
        '    assert "expand reviewed KPI denominators" in roadmap\n',
        '''    assert "two reviewed observations" in roadmap
    assert "eleven reviewed pass outcomes" in roadmap
    assert "`guarded_remediation_promotion`" in roadmap
    assert "expand reviewed KPI denominators" not in roadmap
''',
    )


def validate() -> None:
    for path in (
        "src/sdetkit/product_maturity_radar_portfolio.py",
        "tests/test_product_maturity_radar_portfolio.py",
        "tests/test_platform_capability_matrix.py",
    ):
        ast.parse(Path(path).read_text(encoding="utf-8"), filename=path)
    json.loads(Path("docs/contracts/platform-capability-matrix.v1.json").read_text(encoding="utf-8"))
    for path in (
        "docs/roadmap/product-roadmap.md",
        "docs/operator-reviewed-kpi-portfolio-report.md",
        "src/sdetkit/product_maturity_radar_portfolio.py",
        "tests/test_product_maturity_radar_portfolio.py",
        "tests/test_platform_capability_matrix.py",
    ):
        text = Path(path).read_text(encoding="utf-8")
        if "expand reviewed KPI denominators" in text:
            raise SystemExit(f"{path}: stale denominator-expansion marker remains")
    print("product_control_alignment_validation=pass")


def main() -> None:
    patch_portfolio_source()
    patch_roadmap()
    patch_operator_guide()
    patch_portfolio_tests()
    patch_capability_matrix_test()
    validate()


if __name__ == "__main__":
    main()
