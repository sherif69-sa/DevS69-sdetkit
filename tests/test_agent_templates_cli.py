from __future__ import annotations

import json
from pathlib import Path

from sdetkit.agent import cli


def _seed_template(root: Path) -> None:
    tpl_dir = root / "templates" / "automations"
    tpl_dir.mkdir(parents=True)
    (tpl_dir / "demo.yaml").write_text(
        """
metadata:
  id: demo
  title: Demo
  version: 1.0.0
  description: Demo template
inputs:
  value:
    default: ok
workflow:
  - action: fs.write
    with:
      path: ${{run.output_dir}}/out.txt
      content: ${{inputs.value}}
""".strip()
        + "\n",
        encoding="utf-8",
    )


def test_templates_cli_list_show_run_and_pack(tmp_path: Path, monkeypatch, capsys) -> None:
    _seed_template(tmp_path)
    monkeypatch.chdir(tmp_path)

    assert cli.main(["templates", "list"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert listed["templates"][0]["id"] == "demo"

    assert cli.main(["templates", "show", "demo"]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["metadata"]["id"] == "demo"

    assert (
        cli.main(
            [
                "templates",
                "run",
                "demo",
                "--set",
                "value=done",
                "--output-dir",
                "outputs",
            ]
        )
        == 0
    )
    run_payload = json.loads(capsys.readouterr().out)
    assert run_payload["status"] == "ok"
    assert (tmp_path / "outputs" / "out.txt").read_text(encoding="utf-8") == "done"

    assert cli.main(["templates", "pack", "--output", "bundle.tar"]) == 0
    packed = json.loads(capsys.readouterr().out)
    assert packed["count"] == 1
    assert (tmp_path / "bundle.tar").exists()


def test_templates_cli_run_all(tmp_path: Path, monkeypatch, capsys) -> None:
    _seed_template(tmp_path)
    monkeypatch.chdir(tmp_path)

    assert cli.main(["templates", "run-all", "--output-dir", "runs"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert len(payload["runs"]) == 1
    assert payload["runs"][0]["template"]["id"] == "demo"
    assert payload["runs"][0]["status"] == "ok"
    assert (tmp_path / "runs" / "demo" / "out.txt").read_text(encoding="utf-8") == "ok"
