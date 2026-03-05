from __future__ import annotations

import json
from pathlib import Path

from sdetkit.agent import core


def test_parse_scalar_and_yaml_loader(tmp_path: Path) -> None:
    assert core._parse_scalar(" 42 ") == 42
    assert core._parse_scalar("true") is True
    assert core._parse_scalar("~") is None

    cfg = tmp_path / "c.yaml"
    cfg.write_text(
        """
roles:
  manager: planner
budgets:
  max_steps: 3
safety:
  write_allowlist:
    - .sdetkit/agent/workdir
""".strip()
        + "\n",
        encoding="utf-8",
    )
    raw = core._load_yaml_like(cfg)
    assert raw["budgets"]["max_steps"] == 3
    assert raw["safety"]["write_allowlist"][0] == ".sdetkit/agent/workdir"


def test_doctor_agent_detects_bad_config(tmp_path: Path) -> None:
    cfg = tmp_path / ".sdetkit/agent/config.yaml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(
        """
provider:
  type: unknown
safety:
  write_allowlist:
    - /tmp/bad
budgets:
  max_steps: 0
  max_actions: -1
""".strip()
        + "\n",
        encoding="utf-8",
    )

    report = core.doctor_agent(tmp_path, config_path=cfg)
    assert report["ok"] is False
    checks = {c["name"]: c for c in report["checks"]}
    assert checks["provider"]["ok"] is False
    assert checks["write_allowlist"]["ok"] is False
    assert checks["budgets"]["ok"] is False


def test_history_agent_skips_bad_json(tmp_path: Path) -> None:
    h = tmp_path / ".sdetkit/agent/history"
    h.mkdir(parents=True, exist_ok=True)
    (h / "a.json").write_text("{bad", encoding="utf-8")
    (h / "b.json").write_text(
        json.dumps({"hash": "h", "captured_at": "1", "status": "ok", "task": "t"}), encoding="utf-8"
    )
    rows = core.history_agent(tmp_path, limit=10)
    assert len(rows) == 1 and rows[0]["hash"] == "h"
