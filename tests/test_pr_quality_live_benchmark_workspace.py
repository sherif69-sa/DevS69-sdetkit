from __future__ import annotations

import json
import subprocess
from pathlib import Path

from sdetkit.pr_quality_live_benchmark_workspace import (
    SCHEMA_VERSION,
    main,
    prepare_live_benchmark_workspaces,
    render_markdown,
)
from sdetkit.replayable_benchmark_harness import (
    ANTI_CHEAT_REJECTION_COUNT,
    LIVE_EVIDENCE_SOURCE,
    build_isolated_evidence_report,
    load_scenarios,
)

FIXTURES = Path("tests/fixtures/remediation_benchmark")


def _git_status(root: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "status", "--porcelain=v1"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
        shell=False,
    )
    return completed.stdout.splitlines()


def test_workspace_builder_prepares_six_disposable_git_inputs(tmp_path: Path) -> None:
    manifest = prepare_live_benchmark_workspaces(out_dir=tmp_path / "repositories")

    assert manifest["schema_version"] == SCHEMA_VERSION
    assert manifest["status"] == "prepared"
    assert manifest["scenario_count"] == 6

    rows = {item["repo_name"]: item for item in manifest["scenarios"]}
    assert set(rows) == {
        "oracle",
        "mismatch",
        "mutation",
        "network",
        "unclaimed",
        "shadow",
    }

    oracle_root = Path(rows["oracle"]["repo_root"])
    mismatch_root = Path(rows["mismatch"]["repo_root"])
    mutation_root = Path(rows["mutation"]["repo_root"])
    unclaimed_root = Path(rows["unclaimed"]["repo_root"])
    shadow_root = Path(rows["shadow"]["repo_root"])

    assert _git_status(oracle_root) == [" M src/sdetkit/example.py"]
    assert _git_status(mismatch_root) == ["?? src/sdetkit/unplanned.py"]
    assert _git_status(mutation_root) == [" M src/sdetkit/example.py"]
    assert _git_status(unclaimed_root) == [" M src/sdetkit/example.py"]
    assert _git_status(shadow_root) == [" M src/sdetkit/example.py"]

    assert (mutation_root / "tools" / "runtime_hook.py").exists()
    assert (unclaimed_root / "tools" / "runtime_hook.py").exists()
    assert (shadow_root / "tools" / "runtime_hook.py").exists()

    boundary = manifest["boundary"]
    assert boundary["writes_limited_to_output_directory"] is True
    assert boundary["source_checkout_code_modified"] is False
    assert boundary["automation_allowed"] is False
    assert boundary["merge_authorized"] is False
    assert boundary["semantic_equivalence_proven"] is False


def test_workspace_builder_inputs_feed_live_benchmark_without_authority(tmp_path: Path) -> None:
    manifest = prepare_live_benchmark_workspaces(out_dir=tmp_path / "repositories")
    scenarios = load_scenarios([Path(item["fixture_path"]) for item in manifest["scenarios"]])
    repo_roots = [Path(item["repo_root"]) for item in manifest["scenarios"]]

    report = build_isolated_evidence_report(list(zip(scenarios, repo_roots, strict=True)))

    assert report["report_mode"] == LIVE_EVIDENCE_SOURCE
    assert report["status"] == "passed"
    assert report["scenario_count"] == 6
    assert report["passed_count"] == 6
    assert report["live_evidence"]["git_inventory_verified_count"] == 5
    assert report["live_evidence"]["expected_failed_evidence_count"] == 5
    assert report["live_evidence"]["network_boundary_blocked_count"] == 1
    assert report["live_evidence"][ANTI_CHEAT_REJECTION_COUNT] == 2

    boundary = report["safety_boundary"]
    assert boundary["automation_allowed_count"] == 0
    assert boundary["merge_authorized_count"] == 0
    assert boundary["semantic_equivalence_claimed_count"] == 0
    assert boundary["preserved"] is True


def test_workspace_manifest_markdown_reports_read_only_boundary(tmp_path: Path) -> None:
    markdown = render_markdown(prepare_live_benchmark_workspaces(out_dir=tmp_path / "repositories"))

    assert "Scenarios prepared: `6`" in markdown
    assert "Writes limited to output directory: `true`" in markdown
    assert "Source checkout code modified: `false`" in markdown
    assert "Automation allowed: `false`" in markdown
    assert "Merge authorized: `false`" in markdown
    assert "Semantic equivalence proven: `false`" in markdown


def test_workspace_builder_cli_writes_manifest_artifacts(
    tmp_path: Path,
    capsys,
) -> None:
    out_dir = tmp_path / "repositories"

    rc = main(["--out-dir", str(out_dir), "--format", "json"])

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    saved = json.loads((out_dir / "workspace-manifest.json").read_text(encoding="utf-8"))

    assert printed["status"] == "prepared"
    assert printed["scenario_count"] == 6
    assert saved["scenario_count"] == 6
    assert (out_dir / "workspace-manifest.md").exists()
