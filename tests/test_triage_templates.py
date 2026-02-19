from __future__ import annotations

import json
from pathlib import Path

from sdetkit import triage_templates


def test_day9_template_health_payload_is_complete() -> None:
    payload = triage_templates.build_template_health()
    assert payload["name"] == "day9-contribution-templates"
    assert payload["score"] == 100.0
    assert payload["passed_checks"] == payload["total_checks"]
    assert len(payload["templates"]) == 3


def test_markdown_export_writes_day9_artifact(tmp_path: Path) -> None:
    out = tmp_path / "day9.md"
    rc = triage_templates.main(["--format", "markdown", "--output", str(out), "--strict"])
    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert "# Day 9 contribution templates health" in text
    assert "`bug`" in text


def test_json_format_contains_sla_contract() -> None:
    rendered = triage_templates.main(["--format", "json"])
    assert rendered == 0
    payload = json.loads(json.dumps(triage_templates.build_template_health()))
    assert payload["triage_sla"]["first_pr_review"] == "< 48h"
