from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_impact_workflow_map_builds_three_step_phase_aligned_outputs(tmp_path: Path) -> None:
    _write_json(tmp_path / "gate-fast.json", {"ok": True, "failed_steps": []})
    _write_json(tmp_path / "release-preflight.json", {"ok": False, "failed_steps": ["code_scanning"]})
    _write_json(tmp_path / "doctor.json", {"ok": True, "score": 92})

    quality = tmp_path / "quality.sh"
    quality.write_text(
        """
COV_MODE=standard default fail-under 85
COV_MODE=strict default fail-under 95
COV_MODE=legacy compatibility fail-under 80
""".strip()
        + "\n",
        encoding="utf-8",
    )

    out_json = tmp_path / "impact-workflow-map.json"
    out_md = tmp_path / "impact-workflow-map.md"

    proc = subprocess.run(
        [
            sys.executable,
            "scripts/impact_workflow_map.py",
            "--gate-fast",
            str(tmp_path / "gate-fast.json"),
            "--gate-release",
            str(tmp_path / "release-preflight.json"),
            "--doctor",
            str(tmp_path / "doctor.json"),
            "--quality-script",
            str(quality),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert out_json.is_file()
    assert out_md.is_file()

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["current_state"]["gate_release_ok"] is False
    assert payload["impact_workflow"]["step_1"]["id"] == "impact-lock-phases-1-2"
    assert payload["impact_workflow"]["step_3"]["phase_alignment"] == [5, 6]

    markdown = out_md.read_text(encoding="utf-8")
    assert "## 3-Step Impact Workflow" in markdown
    assert "impact-prove-phases-5-6" in markdown
