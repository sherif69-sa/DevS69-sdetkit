from __future__ import annotations

import importlib.util
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from sdetkit import formatter_candidate_benchmark as benchmark

CONTRACT_PATH = Path("docs/contracts/remediation-research.v1.json")
HEAD = "a" * 40


def _fake_runner(argv: Sequence[str], cwd: Path) -> dict[str, Any]:
    command = " ".join(str(item) for item in argv)
    target = cwd / benchmark.TARGET_PATH
    is_format = "format" in argv
    is_check = "--check" in argv
    if is_format and not is_check and argv[-1] == benchmark.TARGET_PATH:
        if target.read_bytes() == benchmark.UNFORMATTED_SOURCE:
            target.write_bytes(benchmark.FORMATTED_SOURCE)
    if is_format and is_check:
        status = "pass" if target.read_bytes() == benchmark.FORMATTED_SOURCE else "fail"
    else:
        status = "pass"
    return {
        "command": command,
        "status": status,
        "exit_code": 0 if status == "pass" else 1,
        "stdout": "",
        "stderr": "",
    }


def _run(tmp_path: Path, *, decision: str = "accept") -> dict[str, Any]:
    return benchmark.run_formatter_candidate_benchmark(
        source_repository="sherif69-sa/DevS69-sdetkit",
        source_commit_sha=HEAD,
        pr_number=2140,
        reviewer_id="maintainer@example.invalid",
        reviewed_at="2026-07-21T00:00:00Z",
        reviewer_decision=decision,
        reviewer_notes="Fixture review record for formatter benchmark contract proof.",
        out_dir=tmp_path / "formatter-benchmark",
        contract_json=CONTRACT_PATH,
        command_runner=_fake_runner,
    )


def test_formatter_candidate_benchmark_proves_six_scenario_contract(tmp_path: Path) -> None:
    report = _run(tmp_path)

    assert report["schema_version"] == benchmark.SCHEMA_VERSION
    assert report["status"] == "passed"
    assert report["candidate_family"] == "formatter_only"
    assert report["scenario_count"] == 6
    assert report["matched_scenario_count"] == 6
    assert report["out_of_scope_write_count"] == 0
    assert report["test_weakening_count"] == 0
    assert report["false_positive_count"] == 0
    assert report["false_positive_cases"] == []
    assert report["rollback_verified"] is True
    assert report["contract_structurally_valid"] is True
    assert report["contract_report_status"] == "review_ready"
    assert report["patch_application_allowed"] is False
    assert report["merge_authorized"] is False
    assert report["semantic_equivalence_proven"] is False

    outcomes = {item["scenario_id"]: item["actual_outcome"] for item in report["scenarios"]}
    assert outcomes == {
        "ambiguous": "blocked",
        "no_op": "pass",
        "oracle": "pass",
        "out_of_scope": "blocked",
        "rollback": "pass",
        "unsafe_patch": "blocked",
    }


def test_formatter_candidate_benchmark_retains_contract_and_scenario_artifacts(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "formatter-benchmark"
    _run(tmp_path)

    expected = {
        benchmark.BENCHMARK_JSON,
        benchmark.BENCHMARK_MD,
        benchmark.EVIDENCE_JSON,
        benchmark.CONTRACT_REPORT_JSON,
        benchmark.CONTRACT_REPORT_MD,
        "proposed.diff",
        "focused-proof.json",
        "full-proof.json",
        "rollback.json",
        "scenario-ambiguous.json",
        "scenario-no_op.json",
        "scenario-oracle.json",
        "scenario-out_of_scope.json",
        "scenario-rollback.json",
        "scenario-unsafe_patch.json",
    }
    assert {path.name for path in out_dir.iterdir()} == expected

    evidence = json.loads((out_dir / benchmark.EVIDENCE_JSON).read_text(encoding="utf-8"))
    assert evidence["pr_owned_scope"] == [benchmark.TARGET_PATH]
    assert evidence["before_inventory"][0]["sha256"] != evidence["after_inventory"][0]["sha256"]
    assert evidence["false_authority_count"] == 0
    assert set(evidence["scenarios"]) == {
        "ambiguous",
        "no_op",
        "oracle",
        "out_of_scope",
        "rollback",
        "unsafe_patch",
    }

    contract_report = json.loads(
        (out_dir / benchmark.CONTRACT_REPORT_JSON).read_text(encoding="utf-8")
    )
    assert contract_report["report_status"] == "review_ready"
    assert contract_report["readiness_reasons"] == []
    assert all(item["matches_expectation"] for item in contract_report["scenario_summary"])


def test_formatter_candidate_benchmark_does_not_mutate_source_repository(tmp_path: Path) -> None:
    sentinel = tmp_path / "source-repository-sentinel.txt"
    sentinel.write_bytes(b"unchanged\n")
    before = sentinel.read_bytes()

    _run(tmp_path)

    assert sentinel.read_bytes() == before


def test_formatter_candidate_benchmark_remains_non_authorizing_when_review_deferred(
    tmp_path: Path,
) -> None:
    report = _run(tmp_path, decision="defer")
    contract_report = json.loads(
        (tmp_path / "formatter-benchmark" / benchmark.CONTRACT_REPORT_JSON).read_text(
            encoding="utf-8"
        )
    )

    assert report["status"] == "passed"
    assert report["contract_report_status"] == "review_required"
    assert "reviewer_has_not_accepted" in contract_report["readiness_reasons"]
    assert report["automation_allowed"] is False
    assert report["publication_authorized"] is False


@pytest.mark.skipif(importlib.util.find_spec("ruff") is None, reason="ruff is a dev dependency")
def test_formatter_candidate_benchmark_runs_pinned_formatter_in_disposable_workspace(
    tmp_path: Path,
) -> None:
    report = benchmark.run_formatter_candidate_benchmark(
        source_repository="sherif69-sa/DevS69-sdetkit",
        source_commit_sha=HEAD,
        pr_number=2140,
        reviewer_id="maintainer@example.invalid",
        reviewed_at="2026-07-21T00:00:00Z",
        reviewer_decision="accept",
        reviewer_notes="Integration proof for the pinned formatter candidate.",
        out_dir=tmp_path / "formatter-integration",
        contract_json=CONTRACT_PATH,
    )

    assert report["status"] == "passed"
    assert report["scenario_count"] == 6
    assert report["rollback_verified"] is True
    assert report["false_positive_count"] == 0


@pytest.mark.skipif(importlib.util.find_spec("ruff") is None, reason="ruff is a dev dependency")
def test_formatter_candidate_benchmark_cli_writes_review_first_artifacts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    out_dir = tmp_path / "formatter-cli"
    rc = benchmark.main(
        [
            "--source-repository",
            "sherif69-sa/DevS69-sdetkit",
            "--source-commit-sha",
            HEAD,
            "--pr-number",
            "2140",
            "--reviewer-id",
            "maintainer@example.invalid",
            "--reviewed-at",
            "2026-07-21T00:00:00Z",
            "--reviewer-decision",
            "defer",
            "--reviewer-notes",
            "Evidence retained for human review; no promotion decision.",
            "--contract-json",
            str(CONTRACT_PATH),
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == "passed"
    assert printed["contract_report_status"] == "review_required"
    assert printed["patch_application_allowed"] is False
    assert (out_dir / benchmark.BENCHMARK_JSON).exists()
    assert (out_dir / benchmark.CONTRACT_REPORT_MD).exists()
