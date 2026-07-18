from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .adoption_product_kpi_freshness import check_freshness, render_freshness_text
from .adoption_product_kpi_model import DEFAULT_CONTRACT, build_report
from .adoption_product_kpi_render import render_markdown

DEFAULT_REPORT = "build/sdetkit/adoption-product-kpi-report.json"


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"invalid JSON object: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def verify_retained_evidence(
    observations_json: str | Path,
    *,
    root: str | Path = ".",
) -> list[dict[str, str]]:
    root_path = Path(root).resolve()
    source_path = Path(observations_json).resolve()
    payload = _load_json_object(source_path)
    observations = payload.get("observations")
    if not isinstance(observations, list):
        raise ValueError("observations must be a list")

    verified: list[dict[str, str]] = []
    for index, observation in enumerate(observations, 1):
        if not isinstance(observation, dict):
            raise ValueError(f"observation {index} must be an object")
        observation_id = str(observation.get("observation_id", "")).strip() or str(index)
        evidence_path = str(observation.get("evidence_path", "")).strip()
        expected_digest = str(observation.get("evidence_sha256", "")).strip().lower()
        candidate = Path(evidence_path)
        if not evidence_path or candidate.is_absolute():
            raise ValueError(
                f"observation {observation_id} evidence_path must be repository-relative"
            )
        resolved = (root_path / candidate).resolve()
        try:
            resolved.relative_to(root_path)
        except ValueError as exc:
            raise ValueError(
                f"observation {observation_id} evidence_path escapes repository root"
            ) from exc
        if not resolved.is_file():
            raise ValueError(f"observation {observation_id} evidence file is missing")
        actual_digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
        if actual_digest != expected_digest:
            raise ValueError(f"observation {observation_id} evidence_sha256 mismatch")
        verified.append(
            {
                "observation_id": observation_id,
                "evidence_path": candidate.as_posix(),
                "evidence_sha256": actual_digest,
            }
        )
    return sorted(verified, key=lambda item: item["observation_id"])


def write_artifacts(
    *,
    observations_json: str | Path,
    out: str | Path = DEFAULT_REPORT,
    markdown_out: str | Path | None = None,
    contract_json: str | Path = DEFAULT_CONTRACT,
    root: str | Path = ".",
    current_head_sha: str | None = None,
    verify_evidence: bool = False,
) -> dict[str, Any]:
    if verify_evidence:
        verify_retained_evidence(observations_json, root=root)
    payload = build_report(
        observations_json,
        contract_json=contract_json,
        root=root,
        current_head_sha=current_head_sha,
    )
    out_path = Path(out)
    markdown_path = Path(markdown_out) if markdown_out else out_path.with_suffix(".md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(payload) + "\n", encoding="utf-8")
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit adoption-product-kpi-report",
        description="Build a deterministic report from reviewed real-repository KPI observations.",
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--observations-json", required=True)
    parser.add_argument("--contract-json", default=DEFAULT_CONTRACT)
    parser.add_argument("--out", default=DEFAULT_REPORT)
    parser.add_argument("--markdown-out", default="")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    parser.add_argument("--check-freshness", action="store_true")
    ns = parser.parse_args(list(argv) if argv is not None else None)

    verify_retained_evidence(ns.observations_json, root=ns.root)
    if ns.check_freshness:
        payload = check_freshness(
            report_path=ns.out,
            observations_json=ns.observations_json,
            contract_json=ns.contract_json,
            root=ns.root,
        )
        output = (
            json.dumps(payload, indent=2, sort_keys=True)
            if ns.format == "json"
            else render_freshness_text(payload)
        )
        sys.stdout.write(output + "\n")
        return 0 if payload["fresh"] else 1

    payload = write_artifacts(
        observations_json=ns.observations_json,
        contract_json=ns.contract_json,
        out=ns.out,
        markdown_out=ns.markdown_out or None,
        root=ns.root,
        verify_evidence=True,
    )
    output = (
        json.dumps(payload, indent=2, sort_keys=True)
        if ns.format == "json"
        else render_markdown(payload)
    )
    sys.stdout.write(output + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
