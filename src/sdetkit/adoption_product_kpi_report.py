from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .adoption_product_kpi_freshness import check_freshness, render_freshness_text
from .adoption_product_kpi_model import DEFAULT_CONTRACT, build_report
from .adoption_product_kpi_render import render_markdown

DEFAULT_REPORT = "build/sdetkit/adoption-product-kpi-report.json"


def write_artifacts(
    *,
    observations_json: str | Path,
    out: str | Path = DEFAULT_REPORT,
    markdown_out: str | Path | None = None,
    contract_json: str | Path = DEFAULT_CONTRACT,
    root: str | Path = ".",
    current_head_sha: str | None = None,
) -> dict[str, Any]:
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
