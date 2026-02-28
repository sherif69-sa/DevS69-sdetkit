import json
from pathlib import Path

from sdetkit import cli
from sdetkit.production_readiness import build_production_readiness_summary


def test_production_readiness_summary_for_repo_has_high_score():
    payload = build_production_readiness_summary(Path("."))

    assert payload["summary"]["score"] >= 90
    assert payload["summary"]["total_checks"] >= 8


def test_production_readiness_cli_emit_pack(tmp_path: Path, capsys):
    pack = tmp_path / "pack"

    rc = cli.main(
        [
            "production-readiness",
            "--format",
            "json",
            "--emit-pack-dir",
            str(pack),
        ]
    )

    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert "summary" in data
    assert (pack / "production-readiness-summary.json").exists()
    assert (pack / "production-readiness-report.md").exists()
