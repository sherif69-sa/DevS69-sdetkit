import json
from pathlib import Path

from sdetkit import cli, phase_boost


def test_build_phase_boost_payload_has_three_phases():
    payload = phase_boost.build_phase_boost_payload("repo-x", "2026-03-01")

    assert payload["repository"] == "repo-x"
    assert payload["duration_window"] == 90
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


def test_phase_boost_parser_defaults_start_date_to_today_iso():
    args = phase_boost._parser().parse_args([])

    assert args.start_date == phase_boost.date.today().isoformat()


def test_phase_boost_rejects_invalid_start_date(capsys) -> None:
    rc = phase_boost.main(["--repo-name", "repo-prod", "--start-date", "not-a-date"])

    captured = capsys.readouterr()
    assert rc != 0
    assert "--start-date must be a valid ISO date" in captured.err


def test_phase_boost_main_valid_start_date_emits_markdown(capsys) -> None:
    rc = phase_boost.main(["--repo-name", "repo-prod", "--start-date", "2026-03-01"])

    captured = capsys.readouterr()
    assert rc == 0
    assert "# Phase boost plan for repo-prod" in captured.out
    assert "- Phase 1 - Baseline hardening (30 days)" in captured.out


def test_phase_boost_main_json_output_contract(tmp_path: Path) -> None:
    out_json = tmp_path / "phase-boost.json"

    rc = phase_boost.main(
        [
            "--repo-name",
            "repo-prod",
            "--start-date",
            "2026-03-01",
            "--json-output",
            str(out_json),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert rc == 0
    assert payload["repository"] == "repo-prod"
    assert payload["start_date"] == "2026-03-01"
    assert payload["goal"] == "S-class production readiness"
    assert isinstance(payload["phases"], list)
