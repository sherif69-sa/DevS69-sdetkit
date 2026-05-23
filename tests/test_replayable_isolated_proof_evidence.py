from __future__ import annotations

import json
import subprocess
from pathlib import Path

from sdetkit.isolated_proof_runner import WORKSPACE_MUTATED_DURING_EXECUTION
from sdetkit.replayable_benchmark_harness import (
    INVENTORY_CLAIM_MISMATCH_FAIL,
    LIVE_EVIDENCE_SOURCE,
    LIVE_EXECUTION_MODEL,
    NETWORK_BOUNDARY_REQUIRED_FAIL,
    PROOF_MUTATION_FAIL,
    build_benchmark_report,
    build_isolated_evidence_report,
    load_scenarios,
    main,
    render_markdown,
)
from sdetkit.repo_memory import LIVE_PROFILE_STATUS, LIVE_PROOF_STATE, build_repo_memory_profile

FIXTURES = Path("tests/fixtures/remediation_benchmark")
LIVE_PATHS = [
    FIXTURES / "live_oracle_git_grounded.json",
    FIXTURES / "live_inventory_claim_mismatch.json",
    FIXTURES / "live_proof_mutation.json",
    FIXTURES / "live_network_boundary_required.json",
]
FIXTURE_PATHS = [
    FIXTURES / "nop_formatting_patch.json",
    FIXTURES / "oracle_formatting_patch.json",
    FIXTURES / "unsafe_protected_path_patch.json",
]


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
        shell=False,
    )
    return completed.stdout.strip()


def _base_repo(tmp_path: Path, name: str, *, mutation_hook: bool = False) -> Path:
    root = tmp_path / name
    source = root / "src" / "sdetkit"
    tests = root / "tests"
    source.mkdir(parents=True)
    tests.mkdir()

    (source / "example.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tests / "test_placeholder.py").write_text(
        "def test_placeholder() -> None:\n    assert True\n",
        encoding="utf-8",
    )

    if mutation_hook:
        tools = root / "tools"
        tools.mkdir()
        (tools / "mutate_example.py").write_text(
            "from pathlib import Path\n"
            'Path("src/sdetkit/example.py").write_text('
            '"VALUE = 99\\n", encoding="utf-8")\n',
            encoding="utf-8",
        )
        (root / ".pre-commit-config.yaml").write_text(
            "repos:\n"
            "  - repo: local\n"
            "    hooks:\n"
            "      - id: mutate-example\n"
            "        name: mutate example in copied workspace\n"
            "        entry: python tools/mutate_example.py\n"
            "        language: system\n"
            "        pass_filenames: false\n"
            "        always_run: true\n",
            encoding="utf-8",
        )

    _git(root, "init", "--quiet")
    _git(root, "config", "user.name", "Live Benchmark Test")
    _git(root, "config", "user.email", "live-benchmark@invalid.local")
    _git(root, "add", "-A")
    _git(root, "commit", "--quiet", "-m", "baseline")
    return root


def _scenario_runs(tmp_path: Path) -> list[tuple[dict, Path]]:
    oracle_root = _base_repo(tmp_path, "oracle")
    (oracle_root / "src" / "sdetkit" / "example.py").write_text(
        "VALUE = 2\n",
        encoding="utf-8",
    )

    mismatch_root = _base_repo(tmp_path, "mismatch")
    (mismatch_root / "src" / "sdetkit" / "unplanned.py").write_text(
        "VALUE = 2\n",
        encoding="utf-8",
    )

    mutation_root = _base_repo(tmp_path, "mutation", mutation_hook=True)
    (mutation_root / "src" / "sdetkit" / "example.py").write_text(
        "VALUE = 2\n",
        encoding="utf-8",
    )

    network_root = _base_repo(tmp_path, "network")
    (network_root / "src" / "sdetkit" / "example.py").write_text(
        "VALUE = 2\n",
        encoding="utf-8",
    )

    scenarios = load_scenarios(LIVE_PATHS)
    return list(
        zip(
            scenarios,
            [oracle_root, mismatch_root, mutation_root, network_root],
            strict=True,
        )
    )


def test_live_benchmark_proves_git_grounded_isolated_evidence_contract(
    tmp_path: Path,
) -> None:
    report = build_isolated_evidence_report(_scenario_runs(tmp_path))

    assert report["schema_version"] == "sdetkit.replayable_benchmark_harness.isolated_evidence.v2"
    assert report["report_mode"] == LIVE_EVIDENCE_SOURCE
    assert report["status"] == "passed"
    assert report["scenario_count"] == 4
    assert report["passed_count"] == 4

    required = report["required_contract"]
    assert required["all_required_present"] is True
    assert required["all_required_passed"] is True
    assert required["oracle_pass_rate"] == 1.0
    assert required["claim_mismatch_rejection_rate"] == 1.0
    assert required["proof_mutation_rejection_rate"] == 1.0

    live = report["live_evidence"]
    assert live["scenario_count"] == 4
    assert live["git_inventory_verified_count"] == 3
    assert live["expected_failed_evidence_count"] == 3
    assert live["network_boundary_blocked_count"] == 1
    assert live["network_isolation_enforced_count"] == 0

    boundary = report["safety_boundary"]
    assert boundary["execution_model"] == LIVE_EXECUTION_MODEL
    assert boundary["automation_allowed_count"] == 0
    assert boundary["merge_authorized_count"] == 0
    assert boundary["semantic_equivalence_claimed_count"] == 0
    assert boundary["preserved"] is True


def test_live_benchmark_oracle_uses_verified_git_inventory_and_passed_proof(
    tmp_path: Path,
) -> None:
    report = build_isolated_evidence_report(_scenario_runs(tmp_path))
    oracle = next(item for item in report["scenarios"] if item["scenario_type"] == "oracle_pass")
    evidence = oracle["isolated_proof_evidence"]
    decision = oracle["protected_verifier_result"]["decision"]

    assert oracle["passed"] is True
    assert evidence["status"] == "passed"
    assert evidence["decision_boundary"]["git_inventory_verified"] is True
    assert decision["status"] == "structurally_verified_candidate"
    assert decision["automation_allowed"] is False
    assert decision["merge_authorized"] is False


def test_live_benchmark_rejects_git_inventory_claim_mismatch(tmp_path: Path) -> None:
    report = build_isolated_evidence_report(_scenario_runs(tmp_path))
    result = next(
        item
        for item in report["scenarios"]
        if item["scenario_type"] == INVENTORY_CLAIM_MISMATCH_FAIL
    )
    evidence = result["isolated_proof_evidence"]

    assert result["passed"] is True
    assert evidence["status"] == "failed"
    assert evidence["decision_boundary"]["git_inventory_verified"] is False
    assert result["protected_verifier_result"]["decision"]["status"] == "blocked_review_first"


def test_live_benchmark_rejects_mutating_allowlisted_proof(tmp_path: Path) -> None:
    report = build_isolated_evidence_report(_scenario_runs(tmp_path))
    result = next(
        item for item in report["scenarios"] if item["scenario_type"] == PROOF_MUTATION_FAIL
    )
    evidence = result["isolated_proof_evidence"]
    proof = evidence["proof_results"][0]

    assert result["passed"] is True
    assert evidence["decision_boundary"]["git_inventory_verified"] is True
    assert proof[WORKSPACE_MUTATED_DURING_EXECUTION] is True
    assert proof["status"] == "failed"
    assert result["protected_verifier_result"]["decision"]["status"] == "blocked_review_first"


def test_live_benchmark_rejects_required_unverified_network_boundary(
    tmp_path: Path,
) -> None:
    report = build_isolated_evidence_report(_scenario_runs(tmp_path))
    result = next(
        item
        for item in report["scenarios"]
        if item["scenario_type"] == NETWORK_BOUNDARY_REQUIRED_FAIL
    )
    evidence = result["isolated_proof_evidence"]
    isolation = evidence["isolation"]

    assert result["passed"] is True
    assert evidence["status"] == "failed"
    assert evidence["proof_results"] == []
    assert isolation["network_isolation_required"] is True
    assert isolation["network_isolation_enforced"] is False
    assert isolation["proof_execution_blocked"] is True
    assert result["protected_verifier_result"]["decision"]["status"] == "blocked_review_first"


def test_live_benchmark_markdown_renders_runtime_boundaries(tmp_path: Path) -> None:
    markdown = render_markdown(build_isolated_evidence_report(_scenario_runs(tmp_path)))

    assert "Mode: `git_grounded_isolated_proof`" in markdown
    assert "Required Git-grounded live-evidence contract" in markdown
    assert "Inventory claim mismatch rejection rate: `1.0000`" in markdown
    assert "Proof mutation rejection rate: `1.0000`" in markdown
    assert "Network boundary rejection rate: `1.0000`" in markdown
    assert "Git inventory verified scenarios: `3`" in markdown
    assert "Network boundary blocked scenarios: `1`" in markdown
    assert "Network isolation enforced scenarios: `0`" in markdown
    assert "executes allowlisted proof profiles in disposable workspace copies" in markdown
    assert "Required network isolation fails closed without a verified backend." in markdown


def test_live_benchmark_cli_writes_runtime_report_artifacts(
    tmp_path: Path,
    capsys,
) -> None:
    runs = _scenario_runs(tmp_path)
    out_dir = tmp_path / "report"
    argv: list[str] = []

    for path, (_, repo_root) in zip(LIVE_PATHS, runs, strict=True):
        argv.extend(["--isolated-scenario", str(path)])
        argv.extend(["--isolated-repo-root", str(repo_root)])
    argv.extend(["--out-dir", str(out_dir), "--format", "json"])

    rc = main(argv)

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    saved = json.loads((out_dir / "benchmark-report.json").read_text(encoding="utf-8"))
    markdown = (out_dir / "benchmark-report.md").read_text(encoding="utf-8")

    assert printed["status"] == "passed"
    assert saved["report_mode"] == LIVE_EVIDENCE_SOURCE
    assert saved["live_evidence"]["git_inventory_verified_count"] == 3
    assert "Git-grounded live-evidence contract" in markdown


def test_live_benchmark_outcomes_feed_read_only_repo_memory(tmp_path: Path) -> None:
    live_report = build_isolated_evidence_report(_scenario_runs(tmp_path))
    fixture_report = build_benchmark_report(load_scenarios(FIXTURE_PATHS))
    pattern_insights = {
        "schema_version": "sdetkit.trajectory_pattern_insights.v1",
        "record_count": 3,
        "recurring_safe_fix_patterns": [
            {
                "failure_class": "formatting_only",
                "action": "run_pre_commit",
                "count": 1,
            }
        ],
        "recurring_review_first_surfaces": [],
    }

    profile = build_repo_memory_profile(
        pattern_insights=pattern_insights,
        benchmark_report=fixture_report,
        live_benchmark_report=live_report,
    )

    assert profile["profile_status"] == LIVE_PROFILE_STATUS
    assert profile["live_safe_candidate_count"] == 1
    assert profile["safe_fix_history"][0]["proof_state"] == LIVE_PROOF_STATE
    assert profile["proof_provenance"]["git_verified_scenario_count"] == 3
    assert len(profile["failure_patterns"]["live_rejections"]) == 3
    assert profile["decision_boundary"]["automation_allowed"] is False
    assert profile["decision_boundary"]["merge_authorized"] is False
    assert profile["decision_boundary"]["semantic_equivalence_proven"] is False
