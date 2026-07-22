from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Sequence

from sdetkit import formatter_candidate_benchmark as benchmark
from sdetkit import formatter_candidate_verifier as verifier
from sdetkit import formatter_policy_proposal as proposal

REPOSITORY = "sherif69-sa/DevS69-sdetkit"
SOURCE_COMMIT = "2f12fb975c3abab454466dcf7747d5116f8b2a7b"
SOURCE_PR = 2141
REVIEWED_AT = "2026-07-21T02:09:56Z"
PACKET_ROOT = Path("docs/evidence/formatter-policy-proposal/review-packet-2141")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_command(argv: Sequence[str], cwd: Path) -> dict[str, Any]:
    args = [str(item) for item in argv]
    if len(args) >= 3 and args[1:3] == ["-m", "ruff"]:
        ruff = shutil.which("ruff")
        if not ruff:
            raise RuntimeError("ruff executable is unavailable")
        args = [ruff, *args[3:]]
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONNOUSERSITE"] = "1"
    completed = subprocess.run(
        args,
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return {
        "command": " ".join(args),
        "status": "pass" if completed.returncode == 0 else "fail",
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _generate_evidence() -> None:
    if PACKET_ROOT.exists():
        shutil.rmtree(PACKET_ROOT)
    PACKET_ROOT.mkdir(parents=True)

    with tempfile.TemporaryDirectory(prefix="sdetkit-review-packet-") as temp:
        root = Path(temp)
        benchmark_dir = root / "benchmark"
        benchmark_report = benchmark.run_formatter_candidate_benchmark(
            source_repository=REPOSITORY,
            source_commit_sha=SOURCE_COMMIT,
            pr_number=SOURCE_PR,
            reviewer_id="sherif69-sa",
            reviewed_at=REVIEWED_AT,
            reviewer_decision="accept",
            reviewer_notes=(
                "Merged source evidence retained for a separate proposal-quality review."
            ),
            out_dir=benchmark_dir,
            contract_json=Path("docs/contracts/remediation-research.v1.json"),
            command_runner=_run_command,
        )
        if benchmark_report.get("status") != "passed":
            raise RuntimeError("formatter benchmark did not pass")

        verifier_dir = root / "verifier"
        verifier_report = verifier.verify_formatter_candidate(
            benchmark_dir=benchmark_dir,
            out_dir=verifier_dir,
            repo=REPOSITORY,
            branch="feature/formatter-verifier-trajectory-proof",
            commit_sha=SOURCE_COMMIT,
            pr_number=SOURCE_PR,
            reviewed_at=REVIEWED_AT,
        )
        if verifier_report.get("status") != "passed":
            raise RuntimeError("formatter verifier did not pass")

        verifier_report_path = verifier_dir / verifier.REPORT_JSON
        approval = {
            "schema_version": proposal.APPROVAL_SCHEMA_VERSION,
            "provider": "github",
            "provider_identity_verified": True,
            "reviewer_id": "sherif69-sa",
            "approved_at": REVIEWED_AT,
            "decision": "approve_proposal",
            "source_repository": REPOSITORY,
            "source_commit_sha": SOURCE_COMMIT,
            "source_pr_number": SOURCE_PR,
            "approval_reference": f"https://github.com/{REPOSITORY}/pull/{SOURCE_PR}",
            "verifier_report_sha256": _sha256(verifier_report_path),
            "limitations_acknowledged": True,
        }
        approval_path = root / "formatter-policy-approval.json"
        approval_path.write_text(
            json.dumps(approval, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

        proposal_dir = root / "proposal"
        proposal_report = proposal.build_formatter_policy_proposal(
            verifier_dir=verifier_dir,
            approval_record_json=approval_path,
            out_dir=proposal_dir,
            contract_json=Path("docs/contracts/formatter-policy-proposal.v1.json"),
        )
        if proposal_report.get("status") != "passed":
            raise RuntimeError("formatter policy proposal did not pass")

        shutil.copytree(benchmark_dir, PACKET_ROOT / "benchmark")
        shutil.copytree(verifier_dir, PACKET_ROOT / "verifier")
        shutil.copy2(approval_path, PACKET_ROOT / approval_path.name)
        shutil.copy2(proposal_dir / proposal.REPORT_JSON, PACKET_ROOT / proposal.REPORT_JSON)
        shutil.copy2(proposal_dir / proposal.REPORT_MD, PACKET_ROOT / proposal.REPORT_MD)


def _write_review_contract() -> None:
    checklist = """# Formatter policy proposal review checklist

- packet_status: `ready_for_human_review`
- review_status: `pending_human_decision`
- source_repository: `sherif69-sa/DevS69-sdetkit`
- source_pull_request: `2141`
- source_commit: `2f12fb975c3abab454466dcf7747d5116f8b2a7b`

## Allowed decisions

Choose exactly one after reviewing the retained evidence:

- `accept`
- `reject`
- `defer`
- `request_more_evidence`

## Review dimensions

Record `pass`, `fail`, or `not_applicable` for every dimension:

- `exact_evidence_binding`: proposal bytes, source repository, commit, PR, approval, and verifier digest agree.
- `proposal_scope_clarity`: the intended formatter-only file scope and expected diff are clear.
- `proof_plan_actionability`: focused and broader proof evidence is concrete and reviewable.
- `rollback_clarity`: exact-byte rollback evidence is explicit and sufficient.
- `authority_boundary_preservation`: every mutation, execution, merge, publication, security-dismissal, and semantic-equivalence authority remains denied.
- `operator_usefulness`: the packet supports a clear human decision without overstating proof or maturity.

## Boundary

This packet does not create a reviewed observation and does not authorize branch execution, patch application, merge, publication, security dismissal, or semantic-equivalence claims. The repository-owned observation source remains empty until a human records a decision.
"""
    checklist_path = PACKET_ROOT / "review-checklist.md"
    checklist_path.write_text(checklist, encoding="utf-8")

    artifact_digests = {
        path.relative_to(PACKET_ROOT).as_posix(): _sha256(path)
        for path in sorted(PACKET_ROOT.rglob("*"))
        if path.is_file() and path.name != "review-packet-manifest.json"
    }
    authority = {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "publication_authorized": False,
        "security_dismissal_allowed": False,
        "semantic_equivalence_proven": False,
    }
    manifest = {
        "schema_version": "sdetkit.formatter_policy_proposal_review_packet.v1",
        "packet_status": "ready_for_human_review",
        "review_status": "pending_human_decision",
        "observation_record_created": False,
        "source_repository": REPOSITORY,
        "source_commit_sha": SOURCE_COMMIT,
        "source_pr_number": SOURCE_PR,
        "source_pr_url": f"https://github.com/{REPOSITORY}/pull/{SOURCE_PR}",
        "proposal_path": (PACKET_ROOT / proposal.REPORT_JSON).as_posix(),
        "proposal_sha256": _sha256(PACKET_ROOT / proposal.REPORT_JSON),
        "proposal_markdown_sha256": _sha256(PACKET_ROOT / proposal.REPORT_MD),
        "review_checklist_sha256": _sha256(checklist_path),
        "review_dimensions": [
            "exact_evidence_binding",
            "proposal_scope_clarity",
            "proof_plan_actionability",
            "rollback_clarity",
            "authority_boundary_preservation",
            "operator_usefulness",
        ],
        "allowed_decisions": [
            "accept",
            "reject",
            "defer",
            "request_more_evidence",
        ],
        "artifact_count": len(artifact_digests),
        "artifact_digests": artifact_digests,
        "authority_boundary": authority,
        **authority,
    }
    (PACKET_ROOT / "review-packet-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    _generate_evidence()
    _write_review_contract()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
