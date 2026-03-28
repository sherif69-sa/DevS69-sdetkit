from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/sdet-super-package.md"

_SECTION_HEADER = "# SDET Super Package"
_REQUIRED_SECTIONS = [
    "## Kit 1: Reliability Gate Kit",
    "## Kit 2: Integration Contract Kit",
    "## Kit 3: Performance + Chaos Kit",
    "## Platform components",
    "## Rollout order",
]

_KIT_BLUEPRINTS: list[dict[str, Any]] = [
    {
        "name": "reliability-gate-kit",
        "purpose": "Deterministic commit-to-release safety checks and evidence enforcement.",
        "pillars": [
            "gate fast and gate release execution",
            "security budget + policy drift detection",
            "evidence scorecards with strict exit criteria",
        ],
        "tests": [
            "tests/test_gate_baseline.py",
            "tests/test_security_gate_policy.py",
            "tests/test_evidence_pack.py",
        ],
        "artifacts": [
            "build/gate-fast.json",
            "build/security-enforce.json",
            "reports/release-readiness.md",
        ],
    },
    {
        "name": "integration-contract-kit",
        "purpose": "API/client reliability with deterministic replay and schema/contract controls.",
        "pillars": [
            "cassette-based API replay to remove flakiness",
            "contract drift detection between client/server payloads",
            "failure triage reports for regressions",
        ],
        "tests": [
            "tests/test_apiget_request_builder.py",
            "tests/test_apiclient_async_pagination.py",
            "tests/test_cassette.py",
        ],
        "artifacts": [
            "artifacts/cassettes/",
            "reports/api-contract-drift.json",
            "reports/integration-triage.md",
        ],
    },
    {
        "name": "performance-chaos-kit",
        "purpose": "Resilience and scale confidence using load, latency budget, and fault-injection checks.",
        "pillars": [
            "latency/error budgets with trend alerts",
            "fault injection and recovery assertions",
            "release blocking on SLO violation evidence",
        ],
        "tests": [
            "tests/test_doctor_diagnostics.py",
            "tests/test_control_plane_ops.py",
            "tests/test_reliability_evidence_pack.py",
        ],
        "artifacts": [
            "reports/slo-budget.json",
            "reports/chaos-recovery.md",
            "reports/perf-regression.csv",
        ],
    },
]

_DAY_DEFAULT_PAGE = """# SDET Super Package

This package defines three distinct SDET kits that can be rolled out independently and combined for enterprise-grade release confidence.

## Kit 1: Reliability Gate Kit

Owns deterministic release confidence outcomes for every change.

Core lanes:

- `python -m sdetkit gate fast`
- `python -m sdetkit gate release`
- `python -m sdetkit security enforce --json --out build/security-enforce.json`

## Kit 2: Integration Contract Kit

Owns API and service contract integrity with replay-first validation.

Core lanes:

- `python -m sdetkit apiget --help`
- `python -m pytest -q tests/test_apiget_request_builder.py tests/test_cassette.py`
- `python -m pytest -q tests/test_apiclient_async_pagination.py`

## Kit 3: Performance + Chaos Kit

Owns resilience, recovery, and budget enforcement under stress.

Core lanes:

- `python -m sdetkit doctor --format json`
- `python -m pytest -q tests/test_control_plane_ops.py tests/test_reliability_evidence_pack.py`
- `python -m pytest -q tests/test_doctor_diagnostics.py`

## Platform components

- Unified evidence directory for all kit outputs.
- Deterministic CI workflow templates with artifact upload.
- Mandatory strict mode checks for release branches.

## Rollout order

1. Land Reliability Gate Kit as baseline gate.
2. Add Integration Contract Kit to reduce external-service regressions.
3. Add Performance + Chaos Kit before high-scale or enterprise rollout.
"""


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sdetkit sdet-package",
        description="Plan and validate a multi-kit SDET package blueprint.",
    )
    p.add_argument("--format", choices=["text", "markdown", "json"], default="text")
    p.add_argument("--root", default=".", help="Repository root where docs live.")
    p.add_argument("--output", default="", help="Optional output file path.")
    p.add_argument("--strict", action="store_true", help="Return non-zero when checks are missing.")
    p.add_argument(
        "--write-defaults",
        action="store_true",
        help="Write/repair the default package blueprint page before validation.",
    )
    p.add_argument(
        "--emit-pack-dir",
        default="",
        help="Optional directory for generated kit manifests and rollout checklist.",
    )
    return p


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _required_commands() -> list[str]:
    return [
        "python -m sdetkit gate fast",
        "python -m sdetkit gate release",
        "python -m pytest -q tests/test_apiget_request_builder.py tests/test_cassette.py",
        "python -m pytest -q tests/test_control_plane_ops.py tests/test_reliability_evidence_pack.py",
    ]


def _missing_checks(page_text: str) -> list[str]:
    checks = [_SECTION_HEADER, *_REQUIRED_SECTIONS, *_required_commands()]
    return [item for item in checks if item not in page_text]


def _write_defaults(base: Path) -> list[str]:
    page = base / _PAGE_PATH
    current = _read(page)
    if current and not _missing_checks(current):
        return []
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(_DAY_DEFAULT_PAGE, encoding="utf-8")
    return [_PAGE_PATH]


def _emit_pack(base: Path, out_dir: str) -> list[str]:
    root = base / out_dir
    root.mkdir(parents=True, exist_ok=True)

    created: list[Path] = []
    for kit in _KIT_BLUEPRINTS:
        target = root / f"{kit['name']}.json"
        target.write_text(json.dumps(kit, indent=2) + "\n", encoding="utf-8")
        created.append(target)

    checklist = root / "rollout-checklist.md"
    checklist.write_text(
        "\n".join(
            [
                "# SDET super package rollout checklist",
                "",
                "- [ ] Reliability Gate Kit runs in PR and main branches.",
                "- [ ] Integration Contract Kit cassettes are versioned and deterministic.",
                "- [ ] Performance + Chaos Kit has SLO budgets and recovery reports.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    created.append(checklist)

    return [str(path.relative_to(base)) for path in created]


def build_sdet_package_status(root: str = ".") -> dict[str, Any]:
    base = Path(root)
    page = base / _PAGE_PATH
    page_text = _read(page)
    missing = _missing_checks(page_text)

    total_checks = len([_SECTION_HEADER, *_REQUIRED_SECTIONS, *_required_commands()])
    passed_checks = total_checks - len(missing)
    score = round((passed_checks / total_checks) * 100, 1) if total_checks else 0.0

    return {
        "name": "sdet-super-package",
        "score": score,
        "total_checks": total_checks,
        "passed_checks": passed_checks,
        "page": str(page),
        "kits": _KIT_BLUEPRINTS,
        "missing": missing,
    }


def _render_text(payload: dict[str, Any]) -> str:
    lines = [
        "SDET super package report",
        f"Score: {payload['score']} ({payload['passed_checks']}/{payload['total_checks']})",
        f"Page: {payload['page']}",
        "",
        "Kits:",
    ]
    for kit in payload["kits"]:
        lines.append(f"- {kit['name']}: {kit['purpose']}")
    if payload["missing"]:
        lines.append("")
        lines.append("Coverage gaps:")
        for item in payload["missing"]:
            lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# SDET super package report",
        "",
        f"- Score: **{payload['score']}** ({payload['passed_checks']}/{payload['total_checks']})",
        f"- Page: `{payload['page']}`",
        "",
        "## Kits",
    ]
    for kit in payload["kits"]:
        lines.extend(
            [
                f"### {kit['name']}",
                f"{kit['purpose']}",
                "",
                "- Pillars:",
                *[f"  - {item}" for item in kit["pillars"]],
                "- Tests:",
                *[f"  - `{item}`" for item in kit["tests"]],
                "- Artifacts:",
                *[f"  - `{item}`" for item in kit["artifacts"]],
                "",
            ]
        )
    lines.append("## Coverage gaps")
    if payload["missing"]:
        lines.extend([f"- `{item}`" for item in payload["missing"]])
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    ns = _build_parser().parse_args(list(argv) if argv is not None else None)

    touched_files: list[str] = []
    pack_files: list[str] = []
    base = Path(ns.root)

    if ns.write_defaults:
        touched_files = _write_defaults(base)

    if ns.emit_pack_dir:
        pack_files = _emit_pack(base, ns.emit_pack_dir)

    payload = build_sdet_package_status(ns.root)
    payload["touched_files"] = touched_files
    payload["pack_files"] = pack_files

    if ns.format == "json":
        rendered = json.dumps(payload, indent=2)
    elif ns.format == "markdown":
        rendered = _render_markdown(payload)
    else:
        rendered = _render_text(payload)

    print(rendered)

    if ns.output:
        out = Path(ns.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered, encoding="utf-8")

    if ns.strict and payload["missing"]:
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
