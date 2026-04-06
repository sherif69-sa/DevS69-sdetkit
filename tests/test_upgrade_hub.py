from __future__ import annotations

import json

from sdetkit import upgrade_hub


def test_build_upgrade_hub_summary_includes_plan_inventory(tmp_path) -> None:
    (tmp_path / "src" / "sdetkit").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "sdetkit" / "alpha_closeout_1.py").write_text("", encoding="utf-8")

    plans_dir = tmp_path / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    (plans_dir / "plan-a.json").write_text(
        json.dumps(
            {
                "owner": "release-ops",
                "baseline": {"strict_pass_rate": 0.9},
                "target": {"strict_pass_rate": 1.0},
            }
        ),
        encoding="utf-8",
    )
    (plans_dir / "broken.json").write_text("{broken", encoding="utf-8")

    summary = upgrade_hub.build_upgrade_hub_summary(tmp_path)
    plan_inventory = summary["plan_inventory"]

    assert plan_inventory["total_plan_files"] == 2
    assert plan_inventory["valid_plan_files"] == 1
    assert "plans/broken.json" in plan_inventory["invalid_plan_files"]
    assert plan_inventory["owners"] == ["release-ops"]
    assert plan_inventory["top_upgrade_candidates"][0]["metric"] == "strict_pass_rate"
    assert plan_inventory["top_upgrade_candidates"][0]["delta"] == 0.1


def test_upgrade_hub_main_text_mode_prints_plan_upgrade_lines(tmp_path, capsys) -> None:
    (tmp_path / "src" / "sdetkit").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "sdetkit" / "beta_closeout_2.py").write_text("", encoding="utf-8")

    plans_dir = tmp_path / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    (plans_dir / "plan-b.json").write_text(
        json.dumps(
            {
                "owner": "docs-ops",
                "baseline": {"doc_link_coverage": 0.5},
                "target": {"doc_link_coverage": 0.8},
            }
        ),
        encoding="utf-8",
    )

    rc = upgrade_hub.main(["--format", "text", "--root", str(tmp_path), "--top", "3"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "upgrade-hub" in out
    assert "plans: 1/1 valid" in out
    assert "top plan upgrades:" in out
    assert "doc_link_coverage: +0.3" in out
