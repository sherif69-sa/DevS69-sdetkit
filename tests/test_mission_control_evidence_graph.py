from __future__ import annotations

import json
from pathlib import Path

from sdetkit import mission_control


def _eg_line(name: str, value: object) -> str:
    prefix = "evidence" + "_graph"
    return f"{prefix}_{name}={value}"


def _write_evidence_graph(root: Path) -> Path:
    graph_dir = root / "evidence-graph"
    graph_dir.mkdir(parents=True)
    graph_path = graph_dir / "evidence-graph.json"
    markdown_path = graph_dir / "evidence-graph.md"
    manifest_path = graph_dir / "evidence-graph-manifest.json"

    graph = {
        "schema_version": "sdetkit.evidence-graph.v1",
        "nodes": [
            {
                "source": "sentinel",
                "finding_id": "sentinel-security-001",
                "title": "Security surface changed",
                "summary": "A security-owned surface needs review.",
                "risk_surface": "security",
                "severity": "critical",
                "review_first": True,
                "safe_to_auto_fix": False,
                "owner_files": ["docs/security-posture.md"],
                "source_artifacts": ["build/sdetkit/adaptive-sentinel/control-room.json"],
                "recommended_commands": [
                    "python -m pytest -q tests/test_owned_surface_hygiene_contract.py -o addopts="
                ],
                "proof_commands": ["python -m pre_commit run -a"],
                "recurrence_state": "first_seen",
                "operator_action": "review",
                "automation_allowed_now": False,
            }
        ],
        "source_summary": [
            {
                "source": "sentinel",
                "path": "build/sdetkit/adaptive-sentinel/control-room.json",
                "found": True,
                "status": "attention_required",
                "findings_seen": 1,
                "findings_emitted": 1,
            }
        ],
    }

    graph_path.write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text("# Evidence Graph\n", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.evidence-graph.v1",
                "graph_path": graph_path.as_posix(),
                "markdown_path": markdown_path.as_posix(),
                "node_count": 1,
                "automation_allowed_now": False,
                "sources": graph["source_summary"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return graph_path


def _jsonl_records(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def test_mission_control_run_summarizes_evidence_graph(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    out_dir = tmp_path / "out"
    graph_path = _write_evidence_graph(tmp_path)

    rc = mission_control.main(
        [
            "run",
            "--repo",
            str(repo),
            "--out-dir",
            str(out_dir),
            "--evidence-graph",
            str(graph_path),
            "--no-ledger",
        ]
    )

    assert rc == 0

    bundle = json.loads((out_dir / "mission-control.json").read_text(encoding="utf-8"))
    summary = bundle["evidence_graph"]

    assert bundle["decision"] == "SHIP_WITH_FINDINGS"
    assert bundle["risk_band"] == "medium"
    assert bundle["findings"][0]["code"] == "EVIDENCE_GRAPH_FINDINGS"
    assert summary["enabled"] is True
    assert summary["ok"] is False
    assert summary["status"] == "review_required"
    assert summary["node_count"] == 1
    assert summary["review_first_count"] == 1
    assert summary["critical_count"] == 1
    assert summary["automation_allowed_now"] is False
    assert summary["risk_surfaces"] == ["security"]
    assert summary["top_blocker_surface"] == "security"
    assert summary["top_blocker_title"] == "Security surface changed"
    assert summary["top_blocker_action"] == "review"
    assert summary["next_commands"] == [
        "python -m pre_commit run -a",
        "python -m pytest -q tests/test_owned_surface_hygiene_contract.py -o addopts=",
    ]
    assert summary["source_count"] == 1

    labels = {artifact["label"] for artifact in bundle["artifacts"]}
    assert "Cross-system evidence graph" in labels
    assert "Cross-system evidence graph report" in labels
    assert "Cross-system evidence graph manifest" in labels

    markdown = (out_dir / "mission-control.md").read_text(encoding="utf-8")
    assert "## Evidence Graph" in markdown
    assert "Node count: 1" in markdown
    assert "Review-first nodes: 1" in markdown
    assert "Automation allowed now: false" in markdown
    assert "Top blocker: Security surface changed" in markdown
    assert "Top blocker surface: security" in markdown


def test_mission_control_summarize_prints_evidence_graph(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    out_dir = tmp_path / "out"
    graph_path = _write_evidence_graph(tmp_path)

    assert (
        mission_control.main(
            [
                "run",
                "--repo",
                str(repo),
                "--out-dir",
                str(out_dir),
                "--evidence-graph",
                str(graph_path),
                "--no-ledger",
            ]
        )
        == 0
    )

    capsys.readouterr()
    rc = mission_control.main(["summarize", "--bundle", str(out_dir / "mission-control.json")])

    assert rc == 0
    output = capsys.readouterr().out
    assert _eg_line("ok", "false") in output
    assert _eg_line("status", "review_required") in output
    assert _eg_line("node_count", 1) in output
    assert _eg_line("review_first_count", 1) in output
    assert _eg_line("critical_count", 1) in output
    assert _eg_line("automation_allowed_now", "false") in output
    assert _eg_line("top_blocker_surface", "security") in output
    assert _eg_line("top_blocker_title", "Security surface changed") in output
    assert _eg_line("top_blocker_action", "review") in output


def test_mission_control_ledger_records_evidence_graph_summary(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    out_dir = tmp_path / "out"
    ledger_path = tmp_path / "runs" / "mission-control.jsonl"
    graph_path = _write_evidence_graph(tmp_path)

    rc = mission_control.main(
        [
            "run",
            "--repo",
            str(repo),
            "--out-dir",
            str(out_dir),
            "--evidence-graph",
            str(graph_path),
            "--ledger-path",
            str(ledger_path),
        ]
    )

    assert rc == 0

    records = _jsonl_records(ledger_path)
    summary = records[0]["evidence_graph"]
    assert isinstance(summary, dict)
    assert summary["ok"] is False
    assert summary["status"] == "review_required"
    assert summary["node_count"] == 1
    assert summary["review_first_count"] == 1
    assert summary["critical_count"] == 1
    assert summary["automation_allowed_now"] is False
    assert summary["risk_surfaces"] == ["security"]


def test_mission_control_schema_mentions_evidence_graph(capsys) -> None:
    rc = mission_control.main(["schema"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert "evidence_graph" in payload["required_top_level_keys"]
    assert "evidence_graph" in payload["ledger_record_keys"]
    assert "Evidence Graph" in payload["report_sections"]


def test_mission_control_evidence_graph_ranks_top_blocker(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    out_dir = tmp_path / "out"

    graph_dir = tmp_path / "evidence-graph"
    graph_dir.mkdir()
    graph_path = graph_dir / "evidence-graph.json"
    (graph_dir / "evidence-graph.md").write_text("# Evidence Graph\n", encoding="utf-8")
    graph_path.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.evidence-graph.v1",
                "nodes": [
                    {
                        "finding_id": "quality-coverage",
                        "title": "Coverage gate regression",
                        "summary": "Coverage dropped below threshold.",
                        "risk_surface": "quality",
                        "severity": "warning",
                        "review_first": True,
                        "safe_to_auto_fix": False,
                        "recommended_commands": ["bash quality.sh cov"],
                        "proof_commands": ["bash quality.sh cov"],
                        "operator_action": "review",
                        "automation_allowed_now": False,
                    },
                    {
                        "finding_id": "dependency-resolver",
                        "title": "Dependency resolver failed",
                        "summary": "pip could not resolve constraints before tests ran.",
                        "risk_surface": "dependency",
                        "severity": "warning",
                        "review_first": True,
                        "safe_to_auto_fix": False,
                        "recommended_commands": [
                            "Reproduce the exact install lane.",
                        ],
                        "proof_commands": [
                            "PYTHONPATH=src python -m pip install -c constraints-ci.txt -r requirements-test.txt -e ."
                        ],
                        "operator_action": "review",
                        "automation_allowed_now": False,
                    },
                ],
                "source_summary": [
                    {
                        "source": "failure_bundle",
                        "path": "build/pr-quality/failure-intelligence/failure-bundle.json",
                        "found": True,
                        "status": "needs_fix",
                        "findings_seen": 2,
                        "findings_emitted": 2,
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    rc = mission_control.main(
        [
            "run",
            "--repo",
            str(repo),
            "--out-dir",
            str(out_dir),
            "--evidence-graph",
            str(graph_path),
            "--no-ledger",
        ]
    )

    assert rc == 0
    bundle = json.loads((out_dir / "mission-control.json").read_text(encoding="utf-8"))
    summary = bundle["evidence_graph"]

    assert summary["top_blocker_surface"] == "dependency"
    assert summary["top_blocker_title"] == "Dependency resolver failed"
    assert summary["top_blocker_action"] == "review"
    assert summary["top_blocker_review_first"] is True
    assert summary["next_commands"] == [
        "PYTHONPATH=src python -m pip install -c constraints-ci.txt -r requirements-test.txt -e .",
        "Reproduce the exact install lane.",
    ]

    markdown = (out_dir / "mission-control.md").read_text(encoding="utf-8")
    assert "Top blocker: Dependency resolver failed" in markdown
    assert "Top blocker surface: dependency" in markdown
    assert "Top blocker action: review" in markdown
    assert "PYTHONPATH=src python -m pip install -c constraints-ci.txt" in markdown
