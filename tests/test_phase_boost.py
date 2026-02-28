import json
from pathlib import Path

from sdetkit import cli, phase_boost


def test_build_phase_boost_payload_has_three_phases():
    payload = phase_boost.build_phase_boost_payload("repo-x", "2026-03-01")

    assert payload["repository"] == "repo-x"
    assert payload["duration_days"] == 90
    assert len(payload["phases"]) == 3
    assert payload["phases"][0]["phase"].startswith("Phase 1")


def test_phase_boost_cli_writes_markdown_and_json(tmp_path: Path):
    md = tmp_path / "plan.md"
    js = tmp_path / "plan.json"

    rc = cli.main(
        [
            "phase-boost",
            "--repo-name",
            "repo-prod",
            "--start-date",
            "2026-03-01",
            "--output",
            str(md),
            "--json-output",
            str(js),
        ]
    )

    assert rc == 0
    assert md.exists()
    assert js.exists()

    md_text = md.read_text(encoding="utf-8")
    payload = json.loads(js.read_text(encoding="utf-8"))

    assert "S-class production readiness" in md_text
    assert payload["repository"] == "repo-prod"
