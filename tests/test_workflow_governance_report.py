from __future__ import annotations

import json
from pathlib import Path

from sdetkit.workflow_governance_report import (
    SCHEMA_VERSION,
    analyze_workflow,
    build_workflow_governance_report,
    write_workflow_governance_report,
)


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_workflow_governance_detects_professional_workflow_contract(tmp_path: Path) -> None:
    workflow = _write(
        tmp_path / ".github" / "workflows" / "ci.yml",
        """
name: ci

on:
  pull_request:
  push:

permissions:
  contents: read

concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  test:
    name: quality
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@0123456789abcdef0123456789abcdef01234567
      - uses: actions/setup-python@abcdef0123456789abcdef0123456789abcdef01
      - run: python -m pip install -c constraints-ci.txt -e '.[dev,test]'
      - run: make proof-after-format
      - uses: actions/upload-artifact@1111111111111111111111111111111111111111
        with:
          name: proof
          path: build/proof
          retention-days: 7
""",
    )

    payload = analyze_workflow(tmp_path, workflow)

    assert payload["status"] == "passed"
    assert payload["checklist"]["permissions_least_privilege"] == "yes"
    assert payload["checklist"]["actions_pinned_to_sha"] == "yes"
    assert payload["checklist"]["install_uses_constraints"] == "yes"
    assert payload["checklist"]["cache_key_appropriate"] == "not_applicable"
    assert payload["checklist"]["artifacts_have_retention"] == "yes"
    assert payload["findings"] == []
    assert payload["review_first"] is True
    assert payload["safe_to_patch"] is False


def test_workflow_governance_flags_review_first_findings(tmp_path: Path) -> None:
    _write(
        tmp_path / ".github" / "workflows" / "ci.yml",
        """
name: ci
on: [pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python -m pip install -e '.[dev,test]'
      - run: python -m mkdocs build
""",
    )

    payload = build_workflow_governance_report(tmp_path)

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["report_status"] == "review_required"
    assert payload["workflow_count"] == 1
    assert payload["review_required_count"] == 1
    assert payload["finding_counts"]["permissions_least_privilege"] == 1
    assert payload["finding_counts"]["actions_pinned_to_sha"] == 1
    assert payload["finding_counts"]["install_uses_constraints"] == 1
    assert payload["finding_counts"]["docs_build_strict"] == 1
    assert payload["rules"]["advisory_only"] is True
    assert payload["rules"]["workflow_mutation"] is False
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_workflow_governance_writes_json_and_markdown(tmp_path: Path) -> None:
    _write(
        tmp_path / ".github" / "workflows" / "ci.yml",
        """
name: ci
on: [push]
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
""",
    )
    out = tmp_path / "build" / "workflow-governance-report.json"

    payload = write_workflow_governance_report(repo_root=tmp_path, out=out)

    markdown = out.with_suffix(".md")
    assert out.is_file()
    assert markdown.is_file()
    assert json.loads(out.read_text(encoding="utf-8"))["schema_version"] == SCHEMA_VERSION
    assert "# SDETKit workflow governance report" in markdown.read_text(encoding="utf-8")
    assert payload["workflow_count"] == 1


def test_workflow_governance_cli_dispatch(tmp_path: Path, capsys) -> None:
    _write(
        tmp_path / ".github" / "workflows" / "ci.yml",
        """
name: ci
on: [push]
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
""",
    )
    out = tmp_path / "build" / "workflow-governance-report.json"

    from sdetkit.cli import main as cli_main

    rc = cli_main(
        [
            "workflow-governance-report",
            "--root",
            str(tmp_path),
            "--out",
            str(out),
            "--format",
            "text",
        ]
    )

    assert rc == 0
    stdout = capsys.readouterr().out
    assert "# SDETKit workflow governance report" in stdout
    assert "workflow_mutation: false" in stdout
    assert out.is_file()
    assert out.with_suffix(".md").is_file()


def test_workflow_governance_accepts_setup_python_cache_dependency_path(tmp_path: Path) -> None:
    workflow = _write(
        tmp_path / ".github" / "workflows" / "setup-python-cache.yml",
        """
name: setup-python-cache
on: [push]
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@0123456789abcdef0123456789abcdef01234567
      - uses: actions/setup-python@abcdef0123456789abcdef0123456789abcdef01
        with:
          python-version: "3.12"
          cache: "pip"
          cache-dependency-path: |
            pyproject.toml
            requirements-test.txt
            constraints-ci.txt
      - run: python -m pip install -c constraints-ci.txt -e '.[test]'
      - run: python -m pytest -q tests/test_workflow_governance_report.py -o addopts=
""",
    )

    payload = analyze_workflow(tmp_path, workflow)

    assert payload["checklist"]["cache_key_appropriate"] == "yes"
    assert "cache_key_appropriate" not in payload["findings"]


def test_workflow_governance_flags_setup_python_cache_without_dependency_path(
    tmp_path: Path,
) -> None:
    workflow = _write(
        tmp_path / ".github" / "workflows" / "setup-python-cache.yml",
        """
name: setup-python-cache
on: [push]
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@0123456789abcdef0123456789abcdef01234567
      - uses: actions/setup-python@abcdef0123456789abcdef0123456789abcdef01
        with:
          python-version: "3.12"
          cache: "pip"
      - run: python -m pip install -c constraints-ci.txt -e '.[test]'
      - run: python -m pytest -q tests/test_workflow_governance_report.py -o addopts=
""",
    )

    payload = analyze_workflow(tmp_path, workflow)

    assert payload["checklist"]["cache_key_appropriate"] == "no"
    assert "cache_key_appropriate" in payload["findings"]


def test_workflow_governance_report_exposes_top_level_actionability_contract(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / ".github" / "workflows" / "ci.yml",
        """
name: ci
on: [pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python -m pip install -e '.[dev,test]'
""",
    )

    payload = build_workflow_governance_report(tmp_path)

    assert payload["finding_count"] == sum(payload["finding_counts"].values())
    assert payload["advisory_only"] is True
    assert payload["repo_mutation"] is False
    assert payload["review_first"] is True
    assert payload["safe_to_patch"] is False
    assert payload["operator_summary"]["review_first"] is True
    assert payload["operator_summary"]["safe_to_patch"] is False

    summary = payload["actionability_summary"]
    assert summary["workflow_count"] == 1
    assert summary["review_required_count"] == 1
    assert summary["finding_count"] == payload["finding_count"]
    assert summary["ranked_followup_count"] == len(payload["ranked_followups"])
    assert summary["review_first"] is True
    assert summary["safe_to_patch"] is False


def test_workflow_governance_report_ranks_product_followups_without_authority(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / ".github" / "workflows" / "bot.yml",
        """
name: bot
on:
  workflow_dispatch:
permissions:
  contents: write
jobs:
  bot:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@0123456789abcdef0123456789abcdef01234567
      - uses: actions/upload-artifact@1111111111111111111111111111111111111111
        with:
          name: evidence
          path: build/evidence
""",
    )

    payload = build_workflow_governance_report(tmp_path)

    ranked = payload["ranked_followups"]
    assert ranked

    by_finding = {item["finding"]: item for item in ranked}
    assert "permissions_least_privilege" in by_finding
    assert "artifacts_have_retention" in by_finding

    permissions = by_finding["permissions_least_privilege"]
    assert permissions["priority"] == "P1"
    assert permissions["recommended_change_type"] == "workflow_permission_review"
    assert permissions["review_first"] is True
    assert permissions["safe_to_patch"] is False
    assert permissions["sample_workflows"] == [".github/workflows/bot.yml"]

    retention = by_finding["artifacts_have_retention"]
    assert retention["priority"] == "P1"
    assert retention["recommended_change_type"] == "artifact_retention_followup"
    assert retention["review_first"] is True
    assert retention["safe_to_patch"] is False

    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_workflow_governance_markdown_includes_ranked_followups(tmp_path: Path) -> None:
    _write(
        tmp_path / ".github" / "workflows" / "ci.yml",
        """
name: ci
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
""",
    )
    out = tmp_path / "build" / "workflow-governance-report.json"

    write_workflow_governance_report(repo_root=tmp_path, out=out)

    markdown = out.with_suffix(".md").read_text(encoding="utf-8")
    assert "finding_count:" in markdown
    assert "## Ranked follow-up candidates" in markdown
    assert "recommended_change_type" in markdown
    assert "review_first: true" in markdown
    assert "safe_to_patch: false" in markdown


def test_workflow_governance_report_explains_permission_findings_without_authority(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / ".github" / "workflows" / "security.yml",
        """
name: security
on: [push]
permissions:
  contents: read
  security-events: write
jobs:
  codeql:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@0123456789abcdef0123456789abcdef01234567
      - uses: github/codeql-action/upload-sarif@0123456789abcdef0123456789abcdef01234567
        with:
          sarif_file: build/security.sarif
""",
    )

    payload = build_workflow_governance_report(tmp_path)

    assert payload["permission_review_count"] == 1
    entry = payload["permission_review_matrix"][0]
    assert entry["path"] == ".github/workflows/security.yml"
    assert entry["has_permission_finding"] is True
    assert entry["granted_write_scopes"] == ["security-events: write"]
    assert entry["granted_write_scope_count"] == 1
    assert entry["requires_human_review"] is True
    assert entry["safe_to_patch"] is False
    assert entry["recommended_change_type"] == "permission_reason_review"
    assert any("SARIF/code-scanning" in reason for reason in entry["inferred_permission_reasons"])

    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_workflow_governance_markdown_includes_permission_review_matrix(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / ".github" / "workflows" / "bot.yml",
        """
name: bot
on:
  issue_comment:
    types: [created]
permissions:
  contents: read
  issues: write
  pull-requests: write
jobs:
  bot:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/github-script@0123456789abcdef0123456789abcdef01234567
        with:
          script: |
            await github.rest.issues.createComment({})
""",
    )
    out = tmp_path / "build" / "workflow-governance-report.json"

    write_workflow_governance_report(repo_root=tmp_path, out=out)

    markdown = out.with_suffix(".md").read_text(encoding="utf-8")
    assert "## Permission review matrix" in markdown
    assert ".github/workflows/bot.yml" in markdown
    assert "`issues: write`" in markdown
    assert "`pull-requests: write`" in markdown
    assert "requires_human_review: true" in markdown
    assert "safe_to_patch: false" in markdown


def test_workflow_governance_report_exposes_permission_review_playbook(tmp_path: Path) -> None:
    root = tmp_path
    workflow_dir = root / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    (workflow_dir / "bot.yml").write_text(
        """
name: bot
on:
  workflow_dispatch:
permissions:
  issues: write
  pull-requests: write
jobs:
  bot:
    runs-on: ubuntu-latest
    steps:
      - run: gh issue comment 1 --body hi
""".lstrip(),
        encoding="utf-8",
    )

    from sdetkit.workflow_governance_report import build_workflow_governance_report

    payload = build_workflow_governance_report(root)

    assert payload["permission_review_playbook"] == "docs/ci/workflow-permission-review-playbook.md"
    assert payload["permission_review_next_actions"]
    assert payload["permission_review_matrix"]
    assert payload["safe_to_patch"] is False
    assert payload["review_first"] is True


def test_workflow_governance_report_groups_permission_review_intelligence(tmp_path: Path) -> None:
    root = tmp_path
    workflow_dir = root / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)

    (workflow_dir / "issue-bot.yml").write_text(
        """
name: issue bot
on:
  workflow_dispatch:
permissions:
  issues: write
  pull-requests: write
jobs:
  bot:
    runs-on: ubuntu-latest
    steps:
      - run: gh issue comment 1 --body hi
""".lstrip(),
        encoding="utf-8",
    )
    (workflow_dir / "security-upload.yml").write_text(
        """
name: security upload
on:
  workflow_dispatch:
permissions:
  security-events: write
jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - run: echo upload sarif
""".lstrip(),
        encoding="utf-8",
    )
    (workflow_dir / "release.yml").write_text(
        """
name: release
on:
  workflow_dispatch:
permissions:
  contents: write
  attestations: write
  id-token: write
jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - run: echo release
""".lstrip(),
        encoding="utf-8",
    )

    from sdetkit.workflow_governance_report import (
        build_workflow_governance_report,
        render_workflow_governance_markdown,
    )

    payload = build_workflow_governance_report(root)
    summary = payload["permission_review_summary"]
    markdown = render_workflow_governance_markdown(payload)

    assert summary["status"] == "human_review_required"
    assert summary["permission_review_count"] == payload["permission_review_count"]
    assert summary["automatic_permission_reduction_allowed"] is False
    assert summary["safe_to_patch"] is False
    assert summary["review_first"] is True
    assert summary["next_allowed_action"] == "collect_human_review_evidence"
    assert "automatic_permission_reduction" in summary["blocked_actions"]

    groups = {group["kind"]: group for group in summary["groups"]}
    assert "pr_issue_interaction" in groups
    assert "security_upload" in groups
    assert "release_or_provenance" in groups or "repository_mutation" in groups

    assert "## Permission review summary" in markdown
    assert "automatic_permission_reduction_allowed: false" in markdown
    assert "collect_human_review_evidence" in markdown


def test_workflow_governance_report_emits_permission_review_evidence_packet(
    tmp_path: Path,
) -> None:
    workflow = tmp_path / ".github" / "workflows" / "bot.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text(
        """name: bot
on: workflow_dispatch
permissions:
  issues: write
  pull-requests: write
jobs:
  comment:
    runs-on: ubuntu-latest
    steps:
      - run: gh issue comment 1 --body hi
""",
        encoding="utf-8",
    )

    from sdetkit.workflow_governance_report import (
        build_workflow_governance_report,
        render_workflow_governance_markdown,
    )

    payload = build_workflow_governance_report(tmp_path)
    packet = payload["permission_review_evidence_packet"]

    assert packet["schema_version"] == "sdetkit.workflow_permission_review_evidence.v1"
    assert packet["status"] == "human_review_required"
    assert packet["permission_review_count"] == 1
    assert packet["automatic_permission_reduction_allowed"] is False
    assert packet["review_first"] is True
    assert packet["safe_to_patch"] is False
    assert packet["next_allowed_action"] == "collect_human_review_evidence"
    assert "automatic_permission_reduction" in packet["blocked_actions"]
    assert "reviewer decision" in packet["required_human_evidence"]

    task = packet["review_tasks"][0]
    assert task["workflow"] == ".github/workflows/bot.yml"
    assert task["reviewer_decision_required"] is True
    assert task["requires_human_review"] is True
    assert task["safe_to_patch"] is False
    assert "issues: write" in task["granted_write_scopes"]
    assert "pull-requests: write" in task["granted_write_scopes"]
    assert task["recommended_change_type"] == "workflow_permission_review_evidence"

    markdown = render_workflow_governance_markdown(payload)
    assert "## Permission review evidence packet" in markdown
    assert "### Required human evidence" in markdown
    assert "`reviewer decision`" in markdown
    assert "### Permission review tasks" in markdown
    assert ".github/workflows/bot.yml" in markdown


def test_workflow_governance_infers_gh_api_pr_comment_permissions(
    tmp_path: Path,
) -> None:
    workflow = _write(
        tmp_path / ".github" / "workflows" / "pr-comment.yml",
        """
name: PR comment
on: [pull_request]
permissions:
  contents: read
  issues: write
  pull-requests: write
jobs:
  comment:
    runs-on: ubuntu-latest
    steps:
      - run: |
          gh api --method POST \
            "repos/${REPOSITORY}/issues/${PR_NUMBER}/comments"
          gh api --method PATCH \
            "repos/${REPOSITORY}/issues/comments/${COMMENT_ID}"
""",
    )

    payload = build_workflow_governance_report(tmp_path)
    entry = next(
        item
        for item in payload["permission_review_matrix"]
        if item["path"] == ".github/workflows/pr-comment.yml"
    )

    assert entry["granted_write_scopes"] == [
        "issues: write",
        "pull-requests: write",
    ]
    assert entry["inferred_permission_reasons"] == [
        "GitHub API or gh-based PR/issue interaction detected.",
        "PR or issue comment/review API usage detected.",
    ]
    assert entry["requires_human_review"] is True
    assert entry["safe_to_patch"] is False

    workflow_text = workflow.read_text(encoding="utf-8")
    assert "gh api --method POST" in workflow_text
    assert "gh api --method PATCH" in workflow_text
