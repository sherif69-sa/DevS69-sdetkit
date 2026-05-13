from __future__ import annotations

import json
from pathlib import Path

from sdetkit import mission_control

UNKNOWN_REVIEW_REQUIRED = "UNKNOWN" + "_REVIEW" + "_REQUIRED"


def _afb_line(name: str, value: object) -> str:
    prefix = "adaptive" + "_failure" + "_bundle"
    return f"{prefix}_{name}={value}"


def _write_failure_bundle(root: Path, *, status: str = "needs_fix") -> Path:
    bundle_dir = root / "failure-intelligence"
    bundle_dir.mkdir(parents=True)
    artifacts = {
        "diagnosis_json": (bundle_dir / "adaptive-diagnosis.json").as_posix(),
        "pr_comment_markdown": (bundle_dir / "adaptive-diagnosis-comment.md").as_posix(),
        "learning_summary_json": (bundle_dir / "adaptive-learning-summary.json").as_posix(),
        "safe_fix_plan_json": (bundle_dir / "adaptive-safe-fix-plan.json").as_posix(),
        "patch_plan_json": (bundle_dir / "adaptive-patch-plan.json").as_posix(),
        "operator_brief_markdown": (bundle_dir / "operator-brief.md").as_posix(),
        "artifact_manifest_json": (bundle_dir / "artifact-manifest.json").as_posix(),
    }
    for name, value in artifacts.items():
        path = Path(value)
        if path.suffix == ".md":
            path.write_text(f"# {name}\n", encoding="utf-8")
        else:
            path.write_text("{}\n", encoding="utf-8")

    bundle_path = bundle_dir / "failure-intelligence-bundle.json"
    payload = {
        "schema_version": "sdetkit.adaptive.failure_bundle.v1",
        "bundle_path": bundle_path.as_posix(),
        "status": status,
        "primary_diagnosis_code": UNKNOWN_REVIEW_REQUIRED,
        "diagnosis_count": 1,
        "review_first": True,
        "safe_to_auto_fix": False,
        "artifacts": artifacts,
    }
    bundle_path.write_text(json.dumps(payload), encoding="utf-8")
    return bundle_path


def _jsonl_records(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def test_mission_control_run_summarizes_adaptive_failure_bundle(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    out_dir = tmp_path / "out"
    failure_bundle = _write_failure_bundle(tmp_path)

    rc = mission_control.main(
        [
            "run",
            "--repo",
            str(repo),
            "--out-dir",
            str(out_dir),
            "--failure-bundle",
            str(failure_bundle),
            "--no-ledger",
        ]
    )

    assert rc == 0
    bundle = json.loads((out_dir / "mission-control.json").read_text(encoding="utf-8"))
    summary = bundle["adaptive_failure_bundle"]

    assert summary["enabled"] is True
    assert summary["status"] == "needs_fix"
    assert summary["primary_diagnosis_code"] == UNKNOWN_REVIEW_REQUIRED
    assert summary["diagnosis_count"] == 1
    assert summary["review_first"] is True
    assert summary["safe_to_auto_fix"] is False

    labels = {artifact["label"] for artifact in bundle["artifacts"]}
    assert "Adaptive failure intelligence bundle" in labels
    assert "Adaptive failure diagnosis" in labels
    assert "Adaptive failure operator brief" in labels

    markdown = (out_dir / "mission-control.md").read_text(encoding="utf-8")
    assert "## Adaptive Failure Bundle" in markdown
    assert "Primary diagnosis: UNKNOWN_REVIEW_REQUIRED" in markdown
    assert "Review first: true" in markdown
    assert "Safe to auto-fix: false" in markdown


def test_mission_control_summarize_prints_adaptive_failure_bundle(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    out_dir = tmp_path / "out"
    failure_bundle = _write_failure_bundle(tmp_path)

    assert (
        mission_control.main(
            [
                "run",
                "--repo",
                str(repo),
                "--out-dir",
                str(out_dir),
                "--failure-bundle",
                str(failure_bundle),
                "--no-ledger",
            ]
        )
        == 0
    )

    rc = mission_control.main(["summarize", "--bundle", str(out_dir / "mission-control.json")])

    assert rc == 0
    output = capsys.readouterr().out
    assert _afb_line("ok", "false") in output
    assert _afb_line("status", "needs_fix") in output
    assert _afb_line("primary", UNKNOWN_REVIEW_REQUIRED) in output
    assert _afb_line("diagnosis_count", 1) in output
    assert _afb_line("review_first", "true") in output
    assert _afb_line("safe_to_auto_fix", "false") in output


def test_mission_control_ledger_records_adaptive_failure_bundle_summary(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    out_dir = tmp_path / "out"
    ledger_path = tmp_path / "runs" / "mission-control.jsonl"
    failure_bundle = _write_failure_bundle(tmp_path)

    rc = mission_control.main(
        [
            "run",
            "--repo",
            str(repo),
            "--out-dir",
            str(out_dir),
            "--failure-bundle",
            str(failure_bundle),
            "--ledger-path",
            str(ledger_path),
        ]
    )

    assert rc == 0
    records = _jsonl_records(ledger_path)
    assert len(records) == 1
    summary = records[0]["adaptive_failure_bundle"]
    assert isinstance(summary, dict)
    assert summary["status"] == "needs_fix"
    assert summary["primary_diagnosis_code"] == UNKNOWN_REVIEW_REQUIRED
    assert summary["diagnosis_count"] == 1
    assert summary["review_first"] is True
    assert summary["safe_to_auto_fix"] is False


def test_mission_control_schema_mentions_adaptive_failure_bundle(capsys) -> None:
    rc = mission_control.main(["schema"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert "adaptive_failure_bundle" in payload["required_top_level_keys"]
    assert "adaptive_failure_bundle" in payload["ledger_record_keys"]
