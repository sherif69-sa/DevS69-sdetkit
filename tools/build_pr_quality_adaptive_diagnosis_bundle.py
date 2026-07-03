from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

from sdetkit.pr_quality_adaptive_diagnosis import (
    ADAPTIVE_DIAGNOSIS_BUNDLE_MANIFEST_SCHEMA_VERSION,
    AUTHORITY_EXPECTATIONS,
    adaptive_diagnosis_card,
    build_export,
    serialize_export,
    validate_authority,
)

JsonObject = dict[str, Any]
ARTIFACT_NAMES = (
    "adaptive-diagnosis.html",
    "adaptive-diagnosis.md",
    "adaptive-diagnosis.json",
)


def _load_sibling(name: str, filename: str) -> ModuleType:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load renderer: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HTML_RENDERER = _load_sibling(
    "adaptive_diagnosis_html_renderer",
    "render_pr_quality_adaptive_diagnosis.py",
)
MARKDOWN_RENDERER = _load_sibling(
    "adaptive_diagnosis_markdown_renderer",
    "render_pr_quality_adaptive_diagnosis_markdown.py",
)


def _artifact_record(path: Path) -> JsonObject:
    content = path.read_bytes()
    return {
        "path": path.name,
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def build_bundle(model: JsonObject, out_dir: Path) -> JsonObject:
    card = adaptive_diagnosis_card(model)
    if not card:
        raise ValueError("review model has no adaptive diagnosis card")
    validate_authority(card)

    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / ARTIFACT_NAMES[0]
    markdown_path = out_dir / ARTIFACT_NAMES[1]
    json_path = out_dir / ARTIFACT_NAMES[2]

    html_path.write_text(
        HTML_RENDERER.render_adaptive_diagnosis_html(card),
        encoding="utf-8",
        newline="\n",
    )
    markdown_path.write_text(
        MARKDOWN_RENDERER.render_adaptive_diagnosis_markdown(card),
        encoding="utf-8",
        newline="\n",
    )
    json_path.write_text(
        serialize_export(build_export(card)),
        encoding="utf-8",
        newline="\n",
    )

    manifest = {
        "schema_version": ADAPTIVE_DIAGNOSIS_BUNDLE_MANIFEST_SCHEMA_VERSION,
        "status": "passed",
        "authority_validated": True,
        "authority": dict(AUTHORITY_EXPECTATIONS),
        "artifacts": [_artifact_record(out_dir / name) for name in ARTIFACT_NAMES],
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the portable Adaptive Diagnosis evidence bundle."
    )
    parser.add_argument("--review-model", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    model = json.loads(args.review_model.read_text(encoding="utf-8"))
    if not isinstance(model, dict):
        raise ValueError("review model must be a JSON object")
    manifest = build_bundle(model, args.out_dir)
    print("adaptive_diagnosis_bundle=passed")
    print(f"artifact_count={len(manifest['artifacts'])}")
    print(f"out_dir={args.out_dir.as_posix()}")
    print("authority_validated=true")
    print("reporting_only=true")
    print("automation_allowed=false")
    print("merge_authorized=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
