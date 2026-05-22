from __future__ import annotations

import copy
import json
from pathlib import Path

from sdetkit.replayable_benchmark_harness import (
    build_benchmark_report,
    load_scenarios,
)
from sdetkit.repo_memory import (
    build_repo_memory_profile,
    main,
    render_markdown,
)

FIXTURES = Path("tests/fixtures/remediation_benchmark")
SCENARIOS = [
    FIXTURES / "nop_formatting_patch.json",
    FIXTURES / "oracle_formatting_patch.json",
    FIXTURES / "unsafe_protected_path_patch.json",
]


def _benchmark_report() -> dict:
    return build_benchmark_report(load_scenarios(SCENARIOS))


def _pattern_insights() -> dict:
    return {
        "schema_version": "sdetkit.trajectory_pattern_insights.v1",
        "record_count": 5,
        "recurring_safe_fix_patterns": [
            {
                "failure_class": "formatting_only",
                "action": "run_pre_commit",
                "count": 2,
            }
        ],
        "recurring_review_first_surfaces": [
            {
                "value": "security",
                "count": 2,
            }
        ],
    }


def test_repo_memory_records_benchmark_supported_candidate_without_automation() -> None:
    profile = build_repo_memory_profile(
        pattern_insights=_pattern_insights(),
        benchmark_report=_benchmark_report(),
    )

    assert profile["schema_version"] == "sdetkit.repo_memory.v1"
    assert profile["profile_status"] == "benchmark_supported_memory"
    assert profile["memory_mode"] == "read_only_profile"
    assert profile["inputs"]["benchmark_contract_proven"] is True
    assert profile["known_safe_candidate_count"] == 1

    history = profile["safe_fix_history"][0]
    assert history["failure_class"] == "formatting_only"
    assert history["action"] == "run_pre_commit"
    assert history["proof_state"] == "benchmark_supported_candidate"
    assert history["benchmark_supported"] is True
    assert history["automation_allowed"] is False

    boundary = profile["decision_boundary"]
    assert boundary["automation_allowed"] is False
    assert boundary["merge_authorized"] is False
    assert boundary["semantic_equivalence_proven"] is False


def test_repo_memory_records_proof_commands_and_benchmark_rejections() -> None:
    profile = build_repo_memory_profile(
        pattern_insights=_pattern_insights(),
        benchmark_report=_benchmark_report(),
    )

    assert profile["command_profile"]["observed_proof_commands"] == ["python -m pre_commit run -a"]
    assert profile["command_profile"]["commands_executed_by_repo_memory"] is False

    rejections = profile["failure_patterns"]["benchmark_rejections"]
    types = {item["scenario_type"] for item in rejections}
    assert types == {"nop_fail", "unsafe_patch_fail"}
    assert all(item["decision"] == "blocked_review_first" for item in rejections)
    assert all(item["automation_allowed"] is False for item in rejections)


def test_repo_memory_records_review_first_and_flaky_registry_boundaries() -> None:
    profile = build_repo_memory_profile(
        pattern_insights=_pattern_insights(),
        benchmark_report=_benchmark_report(),
    )

    review_first = profile["failure_patterns"]["review_first"]
    assert review_first == [
        {
            "pattern_kind": "review_first_surface",
            "surface": "security",
            "trajectory_count": 2,
            "decision": "review_first",
            "automation_allowed": False,
        }
    ]

    flaky = profile["flaky_test_registry"]
    assert flaky["collection_status"] == "not_collected"
    assert flaky["entries"] == []
    assert "semantic equivalence" in profile["unproven_boundaries"]


def test_repo_memory_does_not_promote_pattern_when_benchmark_contract_fails() -> None:
    benchmark = copy.deepcopy(_benchmark_report())
    benchmark["status"] = "failed"
    benchmark["required_contract"]["all_required_passed"] = False

    profile = build_repo_memory_profile(
        pattern_insights=_pattern_insights(),
        benchmark_report=benchmark,
    )

    assert profile["profile_status"] == "observation_only"
    assert profile["known_safe_candidate_count"] == 0
    history = profile["safe_fix_history"][0]
    assert history["proof_state"] == "trajectory_observed_only"
    assert history["benchmark_supported"] is False
    assert history["automation_allowed"] is False


def test_repo_memory_markdown_renders_memory_and_safety_boundary() -> None:
    markdown = render_markdown(
        build_repo_memory_profile(
            pattern_insights=_pattern_insights(),
            benchmark_report=_benchmark_report(),
        )
    )

    assert "# RepoMemory profile" in markdown
    assert "Status: `benchmark_supported_memory`" in markdown
    assert "Known safe candidates: `1`" in markdown
    assert "proof_state=`benchmark_supported_candidate`" in markdown
    assert "benchmark scenario=`nop-formatting-patch`" in markdown
    assert "Collection status: `not_collected`" in markdown
    assert "Automation allowed: `false`" in markdown
    assert "Semantic equivalence proven: `false`" in markdown


def test_repo_memory_cli_writes_profile_artifacts(tmp_path: Path, capsys) -> None:
    insights_path = tmp_path / "pattern-insights.json"
    benchmark_path = tmp_path / "benchmark-report.json"
    out_dir = tmp_path / "repo-memory"

    insights_path.write_text(json.dumps(_pattern_insights()), encoding="utf-8")
    benchmark_path.write_text(json.dumps(_benchmark_report()), encoding="utf-8")

    rc = main(
        [
            "--pattern-insights",
            str(insights_path),
            "--benchmark-report",
            str(benchmark_path),
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    saved = json.loads((out_dir / "repo-memory-profile.json").read_text(encoding="utf-8"))
    markdown = (out_dir / "repo-memory-profile.md").read_text(encoding="utf-8")

    assert printed["profile_status"] == "benchmark_supported_memory"
    assert printed["known_safe_candidate_count"] == 1
    assert saved["decision_boundary"]["automation_allowed"] is False
    assert "# RepoMemory profile" in markdown
