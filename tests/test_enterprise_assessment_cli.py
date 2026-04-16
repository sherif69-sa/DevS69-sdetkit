from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli


def test_cli_enterprise_assessment_shortcut_json(tmp_path: Path, capsys) -> None:
    rc = cli.main(["enterprise-assessment", "--root", str(tmp_path), "--format", "json"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["score"] < 100


def test_cli_assessment_alias_text(tmp_path: Path, capsys) -> None:
    rc = cli.main(["assessment", "--root", str(tmp_path), "--format", "text"])

    assert rc == 0
    text = capsys.readouterr().out
    assert text.startswith("enterprise-assessment")
