from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "render_repo_visual_snapshot.py"


def _load_snapshot_module():
    spec = importlib.util.spec_from_file_location("render_repo_visual_snapshot", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_snapshot_markdown_contains_scorecard() -> None:
    module = _load_snapshot_module()
    data = module._build_data(
        REPO_ROOT / "README.md",
        REPO_ROOT / "mkdocs.yml",
        REPO_ROOT / "docs/artifacts/case-snippet-closeout-pack/proof-map.csv",
    )

    markdown = module.build_snapshot_markdown(data)

    assert "## Scorecard" in markdown
    assert "Composite readability score" in markdown
    assert "## Signal targets" in markdown


def test_cli_writes_markdown_and_html_without_screenshot(tmp_path: Path) -> None:
    out_md = tmp_path / "snapshot.md"
    out_html = tmp_path / "snapshot.html"

    cmd = [
        sys.executable,
        str(SCRIPT_PATH),
        "--out-md",
        str(out_md),
        "--out-html",
        str(out_html),
    ]

    completed = subprocess.run(cmd, cwd=REPO_ROOT, check=False, capture_output=True, text=True)

    assert completed.returncode == 0, completed.stderr
    assert out_md.exists()
    assert out_html.exists()
    assert "Repo visual snapshot" in out_md.read_text(encoding="utf-8")
    assert "<html lang='en'>" in out_html.read_text(encoding="utf-8")
