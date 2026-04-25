from __future__ import annotations

import json

from sdetkit import readiness


def _seed_repo(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / "tests").mkdir()
    (tmp_path / "artifacts").mkdir()

    (tmp_path / "SECURITY.md").write_text("How to report a vulnerability\nReport via email\n")
    (tmp_path / "RELEASE.md").write_text("Release checklist\n")
    (tmp_path / "QUALITY_PLAYBOOK.md").write_text("quality gate policy\n")
    (tmp_path / "docs" / "index.md").write_text("gate fast -> gate release -> doctor\n")
    (tmp_path / "requirements.lock").write_text("pkg==1.0\n")
    (tmp_path / "poetry.lock").write_text("[[package]]\n")
    (tmp_path / "CODE_OF_CONDUCT.md").write_text("be kind\n")
    (tmp_path / "SUPPORT.md").write_text("support policy\n")
    (tmp_path / "CONTRIBUTING.md").write_text("contributing flow\n")
    (tmp_path / "CHANGELOG.md").write_text("## 2026-04-16\n- release\n")
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text(
        "steps:\n  - run: pytest -q\n  - run: ruff check .\n"
    )

    for index in range(10):
        (tmp_path / "tests" / f"test_sample_{index}.py").write_text(
            "def test_ok():\n    assert True\n"
        )


def _seed_scenario_capacity(tmp_path, count: int):
    test_lines = ["from __future__ import annotations", ""]
    for index in range(count):
        test_lines.append(f"def test_case_{index}():")
        test_lines.append("    assert True")
        test_lines.append("")
    (tmp_path / "tests" / "test_capacity.py").write_text("\n".join(test_lines), encoding="utf-8")


def test_build_readiness_report_missing_files(tmp_path):
    report = readiness.build_readiness_report(tmp_path)

    assert report["schema_version"] == "sdetkit.readiness.v2"
    assert report["score"] == 0.0
    assert report["tier"] == "needs-work"
    assert report["operational_tier"] == "needs-work"
    assert report["top_tier_ready"] is False
    assert report["achievement_level"] == "bronze"
    assert report["top_actions"]
    assert report["adaptive_actions"]
    assert all("priority" in action for action in report["adaptive_actions"])
    assert report["scenario_capacity"]["target_scenarios"] == 250
    assert report["scenario_capacity"]["status"] == "needs-expansion"
    assert report["check_scorecard"]["passed_checks"] == 0
    assert report["check_scorecard"]["missed_checks"] == report["check_scorecard"]["total_checks"]
    assert all("recommendation" in check for check in report["checks"])
    assert all(check["status"] == "miss" for check in report["checks"])


def test_build_readiness_report_seeded_repo_scores_excellent(tmp_path):
    _seed_repo(tmp_path)

    report = readiness.build_readiness_report(tmp_path)

    assert report["schema_version"] == "sdetkit.readiness.v2"
    assert report["score"] == 100.0
    assert report["tier"] == "excellent"
    assert report["operational_tier"] == "strong"
    assert report["top_tier_ready"] is False
    assert report["achievement_level"] == "silver"
    assert report["adaptive_actions"]
    assert report["scenario_capacity"]["target_scenarios"] == 250
    assert report["scenario_capacity"]["detected_scenarios"] == 10
    assert report["scenario_capacity"]["status"] == "needs-expansion"
    assert report["failed_checks"] == []
    assert report["check_scorecard"]["missed_checks"] == 0
    assert all(check["passed"] for check in report["checks"])


def test_build_readiness_report_top_tier_ready_when_scenarios_hit_target(tmp_path):
    _seed_repo(tmp_path)
    _seed_scenario_capacity(tmp_path, 250)

    report = readiness.build_readiness_report(tmp_path)

    assert report["score"] == 100.0
    assert report["tier"] == "excellent"
    assert report["operational_tier"] == "excellent"
    assert report["top_tier_ready"] is True
    assert report["achievement_level"] == "gold"
    assert report["scenario_capacity"]["status"] == "ready"
    assert report["scenario_capacity"]["detected_scenarios"] >= 250


def test_cli_readiness_json_output(capsys):
    rc = readiness.main([".", "--format", "json"])
    assert rc == 0
    out = capsys.readouterr().out

    payload = json.loads(out)
    assert payload["schema_version"] == "sdetkit.readiness.v2"
    assert "checks" in payload


def test_check_recent_changelog_uses_latest_date_not_first_match(tmp_path):
    (tmp_path / "CHANGELOG.md").write_text(
        "## 2024-01-01\n- old\n\n## 2026-02-12\n- latest\n\n## 2025-11-05\n- mid\n",
        encoding="utf-8",
    )

    result = readiness._check_recent_changelog(tmp_path)

    assert result.passed is True
    assert result.evidence == "latest dated entry found: 2026-02-12"


def test_scan_test_scenario_capacity_counts_only_top_level_test_defs(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_mixed.py").write_text(
        "\n".join(
            [
                "def test_top_level_one():",
                "    assert True",
                "",
                "class TestSuite:",
                "    def test_method_should_not_count(self):",
                "        assert True",
                "",
                "def helper():",
                "    def test_nested_should_not_count():",
                "        assert True",
                "    return test_nested_should_not_count",
                "",
                "async def test_async_should_not_count_with_current_regex():",
                "    assert True",
            ]
        ),
        encoding="utf-8",
    )

    capacity = readiness._scan_test_scenario_capacity(tmp_path)

    assert capacity["detected_scenarios"] == 1
