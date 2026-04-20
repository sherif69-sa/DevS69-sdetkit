from __future__ import annotations

import json
from pathlib import Path

from scripts import check_phase4_governance_contract as contract


def _write_baseline_docs(root: Path) -> None:
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "\n".join([
            "# index",
            "- [Versioning and support posture](versioning-and-support.md)",
            "- [Stability levels](stability-levels.md)",
        ])
        + "\n",
        encoding="utf-8",
    )
    (root / "docs/operator-essentials.md").write_text(
        "make phase4-governance-contract\npython scripts/validate_enterprise_contracts.py\n",
        encoding="utf-8",
    )
    for name in ("versioning-and-support.md", "stability-levels.md", "integrations-and-extension-boundary.md"):
        (root / "docs" / name).write_text("ok\n", encoding="utf-8")


def test_release_evidence_complete_and_sorted(tmp_path: Path, monkeypatch) -> None:
    _write_baseline_docs(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert contract.main(["--format", "json", "--last-review-at", "2026-04-01"]) == 0

    payload = json.loads((tmp_path / "build/phase4-governance/phase4-release-evidence.json").read_text())
    assert payload["required_artifacts"] == sorted(payload["required_artifacts"])
    assert payload["discovered_artifacts"] == sorted(payload["discovered_artifacts"])
    assert payload["missing_artifacts"] == sorted(payload["missing_artifacts"])
    assert payload["evidence_status"] == "complete"


def test_release_evidence_incomplete_when_required_missing(tmp_path: Path, monkeypatch) -> None:
    _write_baseline_docs(tmp_path)
    (tmp_path / "docs/versioning-and-support.md").unlink()
    monkeypatch.chdir(tmp_path)
    contract.main(["--format", "json", "--last-review-at", "2026-04-01"])

    payload = json.loads((tmp_path / "build/phase4-governance/phase4-release-evidence.json").read_text())
    assert payload["evidence_status"] == "incomplete"
    assert "docs/versioning-and-support.md" in payload["missing_artifacts"]


def test_release_evidence_markdown_emitted(tmp_path: Path, monkeypatch) -> None:
    _write_baseline_docs(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert contract.main(["--format", "json", "--last-review-at", "2026-04-01"]) == 0

    md_path = tmp_path / "build/phase4-governance/phase4-release-evidence.md"
    assert md_path.exists()
    text = md_path.read_text(encoding="utf-8")
    assert "# Phase 4 release evidence" in text
    assert "evidence_status" in text


def test_release_evidence_markdown_ordering_snapshot(tmp_path: Path, monkeypatch) -> None:
    _write_baseline_docs(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert contract.main(["--format", "json", "--last-review-at", "2026-04-01"]) == 0

    md_path = tmp_path / "build/phase4-governance/phase4-release-evidence.md"
    text = md_path.read_text(encoding="utf-8")
    expected_sequence = [
        "# Phase 4 release evidence",
        "## Required artifacts",
        "`docs/index.md`",
        "`docs/integrations-and-extension-boundary.md`",
        "`docs/operator-essentials.md`",
        "`docs/stability-levels.md`",
        "`docs/versioning-and-support.md`",
        "## Missing artifacts",
        "- none",
        "- generated_at:",
    ]
    cursor = 0
    for token in expected_sequence:
        pos = text.find(token, cursor)
        assert pos >= 0
        cursor = pos + len(token)


def test_release_evidence_markdown_can_be_skipped(tmp_path: Path, monkeypatch) -> None:
    _write_baseline_docs(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert contract.main(["--format", "json", "--no-md", "--last-review-at", "2026-04-01"]) == 0

    md_path = tmp_path / "build/phase4-governance/phase4-release-evidence.md"
    assert not md_path.exists()
