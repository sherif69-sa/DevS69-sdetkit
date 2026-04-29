from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_build_next_10_followups(tmp_path: Path) -> None:
    out_json = tmp_path / "next-10.json"
    out_md = tmp_path / "next-10.md"
    subprocess.run(
        [
            sys.executable,
            "scripts/build_next_10_followups.py",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--format",
            "json",
        ],
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["count"] == 10
    assert len(payload["items"]) == 10
    assert out_md.exists()
