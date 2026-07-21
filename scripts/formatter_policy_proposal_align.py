from __future__ import annotations

import json
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one marker, found {count}: {old[:80]!r}")
    target.write_text(text.replace(old, new), encoding="utf-8")


def write_operator_doc() -> None:
    Path("docs/formatter-policy-proposal.md").write_text(
        """# Formatter policy proposal eligibility

This contract is the final review-first slice in the guarded formatter-remediation research ladder. It binds independently verified formatter-only evidence to one provider-verified human approval record and permits the candidate to enter a **human-reviewed policy proposal**.

It does not alter `SafetyGate`, apply a patch, execute on a branch, mutate `main`, authorize merge or publication, dismiss security findings, or prove semantic equivalence.

## Promotion level

```text
candidate_family=formatter_only
promotion_mode=proposal_only
proposal_eligible=true
execution_eligible=false
branch_execution_allowed=false
safe_fix_allowed=false
review_required=true
safety_gate_policy_changed=false
```

Proposal eligibility means a maintainer may review a future policy change using this evidence. It is not runtime or mutation authority.

## Provider-bound approval record

The approval JSON must identify GitHub as the provider, state that the provider verified the reviewer identity, bind the reviewer and timestamp to `approve_proposal`, match the exact repository, PR, source commit, and verifier-report SHA-256, and acknowledge the proposal limitations.

The local contract checks that binding but does not independently re-authenticate GitHub identity.

## Local command

```bash
python -m sdetkit.formatter_policy_proposal \\
  --verifier-dir build/formatter-candidate-verifier \\
  --approval-record build/formatter-policy-approval.json \\
  --contract-json docs/contracts/formatter-policy-proposal.v1.json \\
  --out-dir build/formatter-policy-proposal \\
  --format json
```

## Outputs

```text
formatter-policy-proposal.json
formatter-policy-proposal.md
```

The command fails closed on stale approval bindings, missing or shadowed evidence, non-formatter families, failed verifier checks, non-review-first trajectories, RepoMemory authority, current-PR decision input, evidence mutation, or any authority expansion.

## Authority boundary

```text
automation_allowed=false
patch_application_allowed=false
merge_authorized=false
publication_authorized=false
security_dismissal_allowed=false
semantic_equivalence_proven=false
```

Dependency, security, release, workflow-permission, public-API, merge-conflict, compiler, linker, unknown, and broad test-logic changes remain review-first.

Any future branch-only execution research requires a distinct product-control issue, isolated branch scope, explicit rollback, independent verification, and a separate human-reviewed PR.
""",
        encoding="utf-8",
    )


def align_docs() -> None:
    docs_map = Path("docs/docs-map.md")
    text = docs_map.read_text(encoding="utf-8")
    marker = "[Formatter verifier and trajectory proof](formatter-verifier-trajectory-proof.md)"
    replacement = marker + ", [Formatter policy proposal eligibility](formatter-policy-proposal.md)"
    if text.count(marker) != 3:
        raise SystemExit(f"docs-map expected three verifier links, found {text.count(marker)}")
    docs_map.write_text(text.replace(marker, replacement), encoding="utf-8")

    replace_once(
        "mkdocs.yml",
        "      - Formatter verifier and trajectory proof: formatter-verifier-trajectory-proof.md\n",
        "      - Formatter verifier and trajectory proof: formatter-verifier-trajectory-proof.md\n"
        "      - Formatter policy proposal eligibility: formatter-policy-proposal.md\n",
    )
    replace_once(
        "docs/roadmap/product-roadmap.md",
        "| Verifier and trajectory proof | The retained formatter packet is independently checked for exact scope, artifact digests, evidence shadowing, proof capture, rollback bytes, and authority boundaries before review-first trajectory and RepoMemory artifacts are written. |\n",
        "| Verifier and trajectory proof | The retained formatter packet is independently checked for exact scope, artifact digests, evidence shadowing, proof capture, rollback bytes, and authority boundaries before review-first trajectory and RepoMemory artifacts are written. |\n"
        "| Formatter policy proposal eligibility | Provider-bound human approval is tied to the exact verifier digest, source PR, source commit, reviewer identity, and timestamp; formatter-only becomes proposal-eligible while execution, patching, merge, publication, security dismissal, and semantic-equivalence authority remain denied. |\n",
    )
    replace_once(
        "docs/roadmap/product-roadmap.md",
        "| 1 | **Conditional narrow policy promotion** | Consider exactly one family only after independent proof and human review. | A separate authenticated contract preserves branch-only scope, rollback, audit, no merge authority, and all denied security, release, dependency, workflow-permission, and semantic-equivalence surfaces. |\n",
        "| 1 | **Formatter proposal observation** | Observe the quality and usefulness of provider-bound formatter policy proposals before considering any execution research. | Reviewed proposal records remain digest-bound and review-first with zero false authority; `formatter_policy_proposal_observation` stays reporting-only and no branch execution lane is active. |\n",
    )

    operator = Path("docs/operator-reviewed-kpi-portfolio-report.md")
    text = operator.read_text(encoding="utf-8")
    if text.count("guarded_remediation_promotion") != 1:
        raise SystemExit("operator guide must contain one old roadmap gap marker")
    text = text.replace("guarded_remediation_promotion", "formatter_policy_proposal_observation")
    text = text.replace(
        "Neither next action authorizes code changes, patch application, SafetyGate policy promotion, or target-repository execution.",
        "Neither next action authorizes patch application, SafetyGate mutation, branch execution, target-repository execution, merge, publication, security dismissal, or semantic-equivalence claims.",
    )
    operator.write_text(text, encoding="utf-8")


def align_capability_truth() -> None:
    matrix_path = Path("docs/contracts/platform-capability-matrix.v1.json")
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    matrix["active_repository_gaps"] = [
        {
            "exit_criteria": "Reviewed provider-bound formatter proposal records retain zero false authority and demonstrate operator value before any distinct execution research is considered.",
            "gap_id": "formatter_policy_proposal_observation",
            "priority": "P2",
            "review_first": True,
            "suggested_owner_files": [
                "src/sdetkit/formatter_policy_proposal.py",
                "docs/contracts/formatter-policy-proposal.v1.json",
                "tests/test_formatter_policy_proposal.py",
            ],
            "title": "Observe formatter policy proposal quality",
        }
    ]
    capabilities = matrix["capabilities"]
    if any(row.get("capability_id") == "formatter_policy_proposal_eligibility" for row in capabilities):
        raise SystemExit("formatter policy proposal capability already exists")
    capabilities.append(
        {
            "authority": "proposal_eligibility_only",
            "capability_id": "formatter_policy_proposal_eligibility",
            "owner_files": [
                "src/sdetkit/formatter_policy_proposal.py",
                "docs/contracts/formatter-policy-proposal.v1.json",
                "docs/formatter-policy-proposal.md",
            ],
            "proof_tests": ["tests/test_formatter_policy_proposal.py"],
            "status": "implemented_and_tested",
            "title": "Provider-bound formatter policy proposal eligibility",
        }
    )
    matrix_path.write_text(json.dumps(matrix, indent=2) + "\n", encoding="utf-8")

    replace_once(
        "src/sdetkit/product_maturity_radar_portfolio.py",
        'ACTIVE_ROADMAP_GAP = "guarded_remediation_promotion"',
        'ACTIVE_ROADMAP_GAP = "formatter_policy_proposal_observation"',
    )
    replace_once(
        "src/sdetkit/product_maturity_radar_portfolio.py",
        '        "guarded_remediation_promotion_active": ACTIVE_ROADMAP_GAP in active_gap_ids,\n',
        '        "formatter_policy_proposal_observation_active": ACTIVE_ROADMAP_GAP in active_gap_ids,\n',
    )


def align_tests() -> None:
    platform_test = Path("tests/test_platform_capability_matrix.py")
    text = platform_test.read_text(encoding="utf-8")
    text = text.replace(
        '    "remediation_research_contract",\n',
        '    "remediation_research_contract",\n    "formatter_policy_proposal_eligibility",\n',
    )
    text = text.replace(
        '    assert {"guarded_remediation_promotion"} == set(gaps)\n',
        '    assert {"formatter_policy_proposal_observation"} == set(gaps)\n',
    )
    text = text.replace(
        '    assert "remediation_research_contract" in capability_ids\n',
        '    assert "remediation_research_contract" in capability_ids\n'
        '    assert "formatter_policy_proposal_eligibility" in capability_ids\n',
    )
    text = text.replace(
        '    assert "`guarded_remediation_promotion`" in roadmap\n',
        '    assert "`formatter_policy_proposal_observation`" in roadmap\n'
        '    assert "Formatter policy proposal eligibility" in roadmap\n',
    )
    platform_test.write_text(text, encoding="utf-8")

    portfolio_test = Path("tests/test_product_maturity_radar_portfolio.py")
    text = portfolio_test.read_text(encoding="utf-8")
    portfolio_test.write_text(
        text.replace("guarded_remediation_promotion", "formatter_policy_proposal_observation"),
        encoding="utf-8",
    )


def align_typing_truth() -> None:
    replace_once(
        "pyproject.toml",
        '  "sdetkit.formatter_candidate_benchmark",\n  "sdetkit.formatter_candidate_verifier",\n',
        '  "sdetkit.formatter_candidate_benchmark",\n  "sdetkit.formatter_candidate_verifier",\n  "sdetkit.formatter_policy_proposal",\n',
    )

    baseline_path = Path("docs/contracts/quality-truth-baseline.v1.json")
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline["typing"]["source_module_count"] = 526
    checked = baseline["typing"]["explicitly_type_checked_modules"]
    if "sdetkit.formatter_policy_proposal" in checked:
        raise SystemExit("formatter policy proposal already present in typing baseline")
    checked.append("sdetkit.formatter_policy_proposal")
    checked.sort()
    baseline_path.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")

    quality_test = Path("tests/test_quality_truth_baseline.py")
    text = quality_test.read_text(encoding="utf-8")
    text = text.replace("== 525", "== 526")
    text = text.replace("assert len(checked) == 37", "assert len(checked) == 38")
    text = text.replace(
        '    assert "sdetkit.formatter_candidate_verifier" in checked\n',
        '    assert "sdetkit.formatter_candidate_verifier" in checked\n'
        '    assert "sdetkit.formatter_policy_proposal" in checked\n',
    )
    text = text.replace(
        '    assert "sdetkit.formatter_candidate_verifier" not in inventory["modules"]\n',
        '    assert "sdetkit.formatter_candidate_verifier" not in inventory["modules"]\n'
        '    assert "sdetkit.formatter_policy_proposal" not in inventory["modules"]\n',
    )
    quality_test.write_text(text, encoding="utf-8")


def main() -> None:
    write_operator_doc()
    align_docs()
    align_capability_truth()
    align_tests()
    align_typing_truth()


if __name__ == "__main__":
    main()
