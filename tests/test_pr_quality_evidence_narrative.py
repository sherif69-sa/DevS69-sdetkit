from __future__ import annotations

import json
from pathlib import Path

from sdetkit import pr_quality_evidence_narrative as narrative


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _graph(path: Path, *, surface: str = "pr_quality") -> Path:
    return _write_json(
        path,
        {
            "schema_version": "sdetkit.evidence-graph.v1",
            "nodes": [
                {
                    "source": "sentinel",
                    "finding_id": "sentinel-pr-quality",
                    "title": "PR Quality comment workflow changed",
                    "summary": "The PR Quality evidence comment path changed.",
                    "risk_surface": surface,
                    "severity": "warning",
                    "review_first": True,
                    "owner_files": [".github/workflows/pr-quality-comment.yml"],
                    "recommended_commands": [
                        "python -m pytest -q tests/test_pr_quality_adaptive_sentinel_workflow.py -o addopts="
                    ],
                    "proof_commands": [
                        "python -m pytest -q tests/test_evidence_graph.py -o addopts="
                    ],
                    "source_artifacts": ["build/sdetkit/sentinel/control-room.json"],
                    "automation_allowed_now": False,
                }
            ],
            "source_summary": [
                {
                    "source": "sentinel",
                    "path": "build/sdetkit/sentinel/control-room.json",
                    "found": True,
                    "status": "warning",
                    "findings_seen": 1,
                    "findings_emitted": 1,
                }
            ],
        },
    )


def test_green_quality_ignores_stale_failure_bundle_and_explains_real_surface(
    tmp_path: Path,
) -> None:
    quality = _write(
        tmp_path / "quality.log",
        "\n".join(
            [
                "quality.sh cov passed",
                "checks: lint + tests + coverage gate are green for this PR run",
                "Total coverage: 96.69%",
            ]
        ),
    )
    graph = _graph(tmp_path / "evidence-graph.json")
    changed = _write(
        tmp_path / "changed-files.txt",
        ".github/workflows/pr-quality-comment.yml\nsrc/sdetkit/evidence_graph.py\n",
    )
    stale_bundle = _write_json(
        tmp_path / "failure-bundle.json",
        {
            "primary_diagnosis_code": "COVERAGE_GATE_REGRESSION",
            "diagnoses": [
                {
                    "code": "COVERAGE_GATE_REGRESSION",
                    "title": "Coverage gate regression",
                }
            ],
        },
    )

    payload = narrative.build_narrative(
        quality_log=quality,
        quality_outcome="success",
        sentinel_control_room=tmp_path / "control-room.json",
        evidence_graph=graph,
        failure_bundle=stale_bundle,
        changed_files=changed,
    )

    markdown = str(payload["markdown"])
    assert payload["quality"]["ok"] is True
    assert payload["primary_signal"]["surface"] == "pr_quality"
    assert "Quality is green, so the review focus is not coverage." in markdown
    assert "PR Quality evidence affects the comment maintainers use" in markdown
    assert "Coverage gate regression" not in markdown
    assert "COVERAGE_GATE_REGRESSION" not in markdown
    assert "What happened" in markdown
    assert "Why it matters" in markdown
    assert "Operator action" in markdown
    assert "Next proof" in markdown


def test_failed_dependency_signal_becomes_primary_blocker(tmp_path: Path) -> None:
    quality = _write(
        tmp_path / "quality.log",
        "pip resolver failed before tests ran\nProcess completed with exit code 1\n",
    )
    bundle = _write_json(
        tmp_path / "failure-bundle.json",
        {
            "primary_diagnosis_code": "PACKAGE_INSTALL_FAILURE",
            "diagnoses": [
                {
                    "code": "PACKAGE_INSTALL_FAILURE",
                    "title": "Dependency resolver failed",
                    "diagnosis": "pip could not resolve constraints.",
                    "proof_commands": [
                        "python -m pip install -c constraints-ci.txt -r requirements-test.txt -e ."
                    ],
                }
            ],
        },
    )

    payload = narrative.build_narrative(
        quality_log=quality,
        quality_outcome="failure",
        sentinel_control_room=None,
        evidence_graph=None,
        failure_bundle=bundle,
        changed_files=None,
    )

    markdown = str(payload["markdown"])
    assert payload["quality"]["ok"] is False
    assert payload["primary_signal"]["kind"] == "actual_failure"
    assert payload["primary_signal"]["surface"] == "dependency"
    assert "Dependency resolver failed" in markdown
    assert "advisory graph findings are secondary" in markdown
    assert "python -m pip install -c constraints-ci.txt" in markdown


def test_green_quality_without_graph_is_concise_and_not_remediation_heavy(tmp_path: Path) -> None:
    quality = _write(tmp_path / "quality.log", "quality.sh cov passed\nTotal coverage: 97.00%\n")

    payload = narrative.build_narrative(
        quality_log=quality,
        quality_outcome="success",
        sentinel_control_room=None,
        evidence_graph=None,
        failure_bundle=None,
        changed_files=None,
    )

    markdown = str(payload["markdown"])
    assert payload["primary_signal"]["kind"] == "green"
    assert "Evidence graph emitted no active findings." in markdown
    assert "No adaptive remediation is recommended." in markdown


def test_cli_writes_markdown_and_json_payload(tmp_path: Path) -> None:
    quality = _write(tmp_path / "quality.log", "quality.sh cov passed\nTotal coverage: 96.50%\n")
    graph = _graph(tmp_path / "evidence-graph.json", surface="diagnostic_engine")
    out = tmp_path / "pr-comment-body.md"
    json_out = tmp_path / "pr-evidence-narrative.json"

    rc = narrative.main(
        [
            "--quality-log",
            str(quality),
            "--quality-outcome",
            "success",
            "--evidence-graph",
            str(graph),
            "--out",
            str(out),
            "--json-out",
            str(json_out),
        ]
    )

    assert rc == 0
    assert "Adaptive release confidence" in out.read_text(encoding="utf-8")
    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == narrative.SCHEMA_VERSION
    assert payload["primary_signal"]["surface"] == "diagnostic_engine"


def test_renderer_includes_graph_markdown_evidence_when_present(tmp_path: Path) -> None:
    quality = _write(tmp_path / "quality.log", "quality.sh cov passed\nTotal coverage: 96.50%\n")
    graph = _graph(tmp_path / "evidence-graph.json")
    _write(tmp_path / "evidence-graph.md", "# Evidence Graph\n")

    payload = narrative.build_narrative(
        quality_log=quality,
        quality_outcome="success",
        sentinel_control_room=None,
        evidence_graph=graph,
        failure_bundle=None,
        changed_files=None,
    )

    markdown = str(payload["markdown"])
    assert "evidence-graph.json" in markdown
    assert "evidence-graph.md" in markdown


def test_green_narrative_prefers_review_surface_proof_over_failure_commands(
    tmp_path: Path,
) -> None:
    quality = _write(
        tmp_path / "quality.log",
        "quality.sh cov passed\nTotal coverage: 96.69%\n",
    )
    graph = _write_json(
        tmp_path / "evidence-graph.json",
        {
            "schema_version": "sdetkit.evidence-graph.v1",
            "nodes": [
                {
                    "title": "Working tree has local changes",
                    "summary": "Sentinel detected uncommitted work; keep proof tied to the current diff.",
                    "risk_surface": "diagnostic_engine",
                    "severity": "warning",
                    "recommended_commands": ["git status -sb", "git diff --stat"],
                },
                {
                    "title": "Adaptive failure bundle signal",
                    "summary": "The PR Quality evidence comment path changed.",
                    "risk_surface": "pr_quality",
                    "severity": "warning",
                    "recommended_commands": [
                        "python -m sdetkit investigate failure --log build/quality.log --format markdown",
                        "python -m sdetkit doctor --diagnose --failure-bundle build/pr-quality/failure-intelligence/failure-intelligence-bundle.json --format json",
                    ],
                },
            ],
            "source_summary": [],
        },
    )
    changed = _write(
        tmp_path / "changed-files.txt",
        ".github/workflows/pr-quality-comment.yml\nsrc/sdetkit/pr_quality_evidence_narrative.py\n",
    )

    payload = narrative.build_narrative(
        quality_log=quality,
        quality_outcome="success",
        sentinel_control_room=None,
        evidence_graph=graph,
        failure_bundle=None,
        changed_files=changed,
    )

    markdown = str(payload["markdown"])
    assert markdown.startswith("✅ quality.sh cov passed")
    assert "## SDET Quality Gate" not in markdown
    assert payload["primary_signal"]["title"] == "PR Quality evidence changed"
    assert payload["primary_signal"]["surface"] == "pr_quality"
    assert "Quality is green, so the review focus is not coverage." in markdown
    assert "python -m sdetkit investigate failure" not in markdown
    assert "python -m sdetkit doctor --diagnose" not in markdown
    assert "git status -sb" not in markdown
    assert "git diff --stat" not in markdown
    assert "tests/test_pr_quality_evidence_narrative.py" in markdown
    assert "python -m pre_commit run -a" in markdown


def test_failed_narrative_keeps_failure_bundle_commands(tmp_path: Path) -> None:
    quality = _write(
        tmp_path / "quality.log",
        "coverage gate failed\nProcess completed with exit code 1\n",
    )
    bundle = _write_json(
        tmp_path / "failure-bundle.json",
        {
            "diagnoses": [
                {
                    "code": "COVERAGE_GATE_REGRESSION",
                    "title": "Coverage gate regression",
                    "diagnosis": "Coverage dropped below the configured threshold.",
                    "proof_commands": ["bash quality.sh cov"],
                }
            ]
        },
    )

    payload = narrative.build_narrative(
        quality_log=quality,
        quality_outcome="failure",
        sentinel_control_room=None,
        evidence_graph=None,
        failure_bundle=bundle,
        changed_files=None,
    )

    markdown = str(payload["markdown"])
    assert payload["primary_signal"]["kind"] == "actual_failure"
    assert "Coverage gate regression" in markdown
    assert "bash quality.sh cov" in markdown


def test_green_narrative_humanizes_generic_pr_quality_graph_title(tmp_path: Path) -> None:
    quality = _write(
        tmp_path / "quality.log",
        "quality.sh cov passed\nTotal coverage: 96.69%\n",
    )
    graph = _write_json(
        tmp_path / "evidence-graph.json",
        {
            "schema_version": "sdetkit.evidence-graph.v1",
            "nodes": [
                {
                    "title": "Adaptive failure bundle signal",
                    "summary": "The PR Quality evidence comment path changed.",
                    "risk_surface": "pr_quality",
                    "severity": "warning",
                    "recommended_commands": [
                        "python -m pytest -q tests/test_pr_quality_evidence_narrative.py -o addopts="
                    ],
                }
            ],
            "source_summary": [],
        },
    )
    changed = _write(
        tmp_path / "changed-files.txt",
        ".github/workflows/pr-quality-comment.yml\nsrc/sdetkit/pr_quality_evidence_narrative.py\n",
    )

    payload = narrative.build_narrative(
        quality_log=quality,
        quality_outcome="success",
        sentinel_control_room=None,
        evidence_graph=graph,
        failure_bundle=None,
        changed_files=changed,
    )

    markdown = str(payload["markdown"])
    assert "PR Quality evidence changed [pr_quality]" in markdown
    assert "Adaptive failure bundle signal [pr_quality]" not in markdown


def test_green_narrative_keeps_specific_non_generic_finding_title(tmp_path: Path) -> None:
    quality = _write(
        tmp_path / "quality.log",
        "quality.sh cov passed\nTotal coverage: 96.69%\n",
    )
    graph = _write_json(
        tmp_path / "evidence-graph.json",
        {
            "schema_version": "sdetkit.evidence-graph.v1",
            "nodes": [
                {
                    "title": "Security-owned surface changed",
                    "summary": "A protected security surface needs review.",
                    "risk_surface": "security",
                    "severity": "critical",
                }
            ],
            "source_summary": [],
        },
    )

    payload = narrative.build_narrative(
        quality_log=quality,
        quality_outcome="success",
        sentinel_control_room=None,
        evidence_graph=graph,
        failure_bundle=None,
        changed_files=None,
    )

    markdown = str(payload["markdown"])
    assert "Security-owned surface changed [security]" in markdown
    assert "Security evidence changed [security]" not in markdown


def test_green_narrative_humanizes_diagnostic_graph_title_from_diff(tmp_path: Path) -> None:
    quality = _write(
        tmp_path / "quality.log",
        "quality.sh cov passed\nTotal coverage: 96.69%\n",
    )
    graph = _write_json(
        tmp_path / "evidence-graph.json",
        {
            "schema_version": "sdetkit.evidence-graph.v1",
            "nodes": [
                {
                    "title": "Evidence graph finding",
                    "summary": "The graph renderer changed.",
                    "risk_surface": "diagnostic_engine",
                    "severity": "warning",
                }
            ],
            "source_summary": [],
        },
    )
    changed = _write(
        tmp_path / "changed-files.txt",
        "src/sdetkit/evidence_graph.py\n",
    )

    payload = narrative.build_narrative(
        quality_log=quality,
        quality_outcome="success",
        sentinel_control_room=None,
        evidence_graph=graph,
        failure_bundle=None,
        changed_files=changed,
    )

    markdown = str(payload["markdown"])
    assert "Diagnostic intelligence evidence changed [diagnostic_engine]" in markdown
    assert "Evidence graph finding [diagnostic_engine]" not in markdown


def test_failed_narrative_ranks_dependency_above_coverage_when_both_exist(
    tmp_path: Path,
) -> None:
    quality = _write(
        tmp_path / "quality.log",
        "quality.sh cov failed\nTotal coverage: 96.69%\nProcess completed with exit code 1\n",
    )
    bundle = _write_json(
        tmp_path / "failure-bundle.json",
        {
            "diagnoses": [
                {
                    "code": "COVERAGE_GATE_REGRESSION",
                    "title": "Coverage gate regression",
                    "diagnosis": "Coverage dropped below threshold.",
                    "proof_commands": ["bash quality.sh cov"],
                },
                {
                    "code": "PACKAGE_INSTALL_FAILURE",
                    "title": "Dependency resolver failed",
                    "diagnosis": "pip could not resolve constraints-ci.txt.",
                    "proof_commands": [
                        "python -m pip install -c constraints-ci.txt -r requirements-test.txt -e ."
                    ],
                },
            ]
        },
    )

    payload = narrative.build_narrative(
        quality_log=quality,
        quality_outcome="failure",
        sentinel_control_room=None,
        evidence_graph=None,
        failure_bundle=bundle,
        changed_files=None,
    )

    markdown = str(payload["markdown"])
    assert payload["primary_signal"]["title"] == "Dependency resolver failed"
    assert payload["primary_signal"]["surface"] == "dependency"
    assert "python -m pip install -c constraints-ci.txt" in markdown
    assert "bash quality.sh cov" not in markdown


def test_failed_narrative_ranks_security_above_dependency_and_coverage(
    tmp_path: Path,
) -> None:
    quality = _write(
        tmp_path / "quality.log",
        "quality.sh cov failed\nProcess completed with exit code 1\n",
    )
    bundle = _write_json(
        tmp_path / "failure-bundle.json",
        {
            "diagnoses": [
                {
                    "code": "PACKAGE_INSTALL_FAILURE",
                    "title": "Dependency resolver failed",
                    "diagnosis": "pip could not resolve requirements.",
                    "proof_commands": ["python -m pip install -e ."],
                },
                {
                    "code": "SECRET_EXPOSURE",
                    "title": "Secret exposure detected",
                    "diagnosis": "A secret-like token was detected in a protected surface.",
                    "severity": "critical",
                    "proof_commands": ["python -m sdetkit security check --root . --format json"],
                },
                {
                    "code": "COVERAGE_GATE_REGRESSION",
                    "title": "Coverage gate regression",
                    "diagnosis": "Coverage dropped below threshold.",
                    "proof_commands": ["bash quality.sh cov"],
                },
            ]
        },
    )

    payload = narrative.build_narrative(
        quality_log=quality,
        quality_outcome="failure",
        sentinel_control_room=None,
        evidence_graph=None,
        failure_bundle=bundle,
        changed_files=None,
    )

    markdown = str(payload["markdown"])
    assert payload["primary_signal"]["title"] == "Secret exposure detected"
    assert payload["primary_signal"]["surface"] == "security"
    assert "python -m sdetkit security check --root . --format json" in markdown
    assert "bash quality.sh cov" not in markdown


def test_failed_narrative_ranks_release_above_quality_tooling(
    tmp_path: Path,
) -> None:
    quality = _write(
        tmp_path / "quality.log",
        "quality.sh cov failed\nProcess completed with exit code 1\n",
    )
    bundle = _write_json(
        tmp_path / "failure-bundle.json",
        {
            "diagnoses": [
                {
                    "code": "RUFF_FORMAT_DRIFT",
                    "title": "Ruff format drift",
                    "diagnosis": "ruff format modified files.",
                    "proof_commands": ["python -m pre_commit run -a"],
                },
                {
                    "code": "RELEASE_ARTIFACT_INVALID",
                    "title": "Release artifact failed twine check",
                    "diagnosis": "twine check failed for dist/*.whl.",
                    "proof_commands": ["python -m build && python -m twine check dist/*"],
                },
            ]
        },
    )

    payload = narrative.build_narrative(
        quality_log=quality,
        quality_outcome="failure",
        sentinel_control_room=None,
        evidence_graph=None,
        failure_bundle=bundle,
        changed_files=None,
    )

    markdown = str(payload["markdown"])
    assert payload["primary_signal"]["title"] == "Release artifact failed twine check"
    assert payload["primary_signal"]["surface"] == "release"
    assert "python -m build && python -m twine check dist/*" in markdown


def test_failed_narrative_ranks_tests_above_coverage_noise(tmp_path: Path) -> None:
    quality = _write(
        tmp_path / "quality.log",
        "FAILED tests/test_real_bug.py::test_behavior\nTotal coverage: 96.69%\n",
    )
    bundle = _write_json(
        tmp_path / "failure-bundle.json",
        {
            "diagnoses": [
                {
                    "code": "COVERAGE_GATE_REGRESSION",
                    "title": "Coverage gate regression",
                    "diagnosis": "Coverage dropped below threshold.",
                    "proof_commands": ["bash quality.sh cov"],
                },
                {
                    "code": "TEST_ASSERTION_FAILURE",
                    "title": "Behavior regression test failed",
                    "diagnosis": "pytest assertion failed in tests/test_real_bug.py.",
                    "proof_commands": [
                        "python -m pytest -q tests/test_real_bug.py::test_behavior -o addopts="
                    ],
                },
            ]
        },
    )

    payload = narrative.build_narrative(
        quality_log=quality,
        quality_outcome="failure",
        sentinel_control_room=None,
        evidence_graph=None,
        failure_bundle=bundle,
        changed_files=None,
    )

    markdown = str(payload["markdown"])
    assert payload["primary_signal"]["title"] == "Behavior regression test failed"
    assert payload["primary_signal"]["surface"] == "tests"
    assert "python -m pytest -q tests/test_real_bug.py::test_behavior -o addopts=" in markdown
    assert "bash quality.sh cov" not in markdown


def test_green_narrative_prioritizes_security_review_graph_signal(tmp_path: Path) -> None:
    quality = _write(
        tmp_path / "quality.log",
        "quality.sh cov passed\nTotal coverage: 96.69%\n",
    )
    graph = _write_json(
        tmp_path / "evidence-graph.json",
        {
            "schema_version": "sdetkit.evidence-graph.v1",
            "nodes": [
                {
                    "title": "Security review requires action in src/sdetkit/adaptive_diagnosis.py",
                    "summary": "GitHub Advanced Security reported an unresolved review finding.",
                    "risk_surface": "security",
                    "severity": "warning",
                    "review_first": True,
                    "safe_to_auto_fix": False,
                    "recommended_commands": [
                        "Review unresolved GitHub Advanced Security comments on the PR.",
                        "Fix the flagged surface or dismiss the false positive with a review reason.",
                    ],
                },
                {
                    "title": "PR Quality evidence changed",
                    "summary": "The PR Quality evidence comment path changed.",
                    "risk_surface": "pr_quality",
                    "severity": "warning",
                },
            ],
            "source_summary": [],
        },
    )
    changed = _write(
        tmp_path / "changed-files.txt",
        "src/sdetkit/adaptive_diagnosis.py\n",
    )

    payload = narrative.build_narrative(
        quality_log=quality,
        quality_outcome="success",
        sentinel_control_room=None,
        evidence_graph=graph,
        failure_bundle=None,
        changed_files=changed,
    )

    markdown = str(payload["markdown"])
    assert payload["primary_signal"]["surface"] == "security"
    assert (
        payload["primary_signal"]["title"]
        == "Security review requires action in src/sdetkit/adaptive_diagnosis.py"
    )
    assert "Quality is green, so the review focus is not coverage." in markdown
    assert "Review unresolved GitHub Advanced Security comments on the PR." in markdown
    assert "Fix the flagged surface or dismiss the false positive with a review reason." in markdown
