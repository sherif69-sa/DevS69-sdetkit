from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_coverage_targets(quality_text: str) -> tuple[int | None, int | None, int | None]:
    standard = re.search(r"COV_MODE=standard[^\n]*fail-under\s*(\d+)", quality_text)
    strict = re.search(r"COV_MODE=strict[^\n]*fail-under\s*(\d+)", quality_text)
    legacy = re.search(r"COV_MODE=legacy[^\n]*fail-under\s*(\d+)", quality_text)
    return (
        int(standard.group(1)) if standard else None,
        int(strict.group(1)) if strict else None,
        int(legacy.group(1)) if legacy else None,
    )


def _status(payload: dict[str, object]) -> bool | None:
    raw = payload.get("ok")
    return raw if isinstance(raw, bool) else None


def build_impact_workflow(
    gate_fast: dict[str, object],
    gate_release: dict[str, object],
    doctor: dict[str, object],
    quality_text: str,
) -> dict[str, object]:
    standard_cov, strict_cov, legacy_cov = _extract_coverage_targets(quality_text)
    release_failed_steps = gate_release.get("failed_steps")
    if not isinstance(release_failed_steps, list):
        release_failed_steps = []

    steps = [
        {
            "id": "impact-lock-phases-1-2",
            "name": "Impact Lock (Phases 1-2)",
            "phase_alignment": [1, 2],
            "goal": "Remove release blockers and lock a reliable baseline before scaling.",
            "priority": "P0",
            "blocked": _status(gate_release) is False,
            "owner_hint": "platform-security",
            "actions": [
                "Run `python -m sdetkit security scan --format sarif --output build/code-scanning.sarif --fail-on high`.",
                "Upload SARIF in CI and block merges on high findings.",
                f"Set coverage gate to fail-under {standard_cov if standard_cov is not None else 85} as minimum baseline.",
            ],
            "success_signal": "gate release passes + baseline coverage stays green",
            "evidence": {
                "failed_steps": release_failed_steps,
                "coverage_standard": standard_cov,
                "coverage_legacy": legacy_cov,
            },
        },
        {
            "id": "impact-accelerate-phases-3-4",
            "name": "Impact Accelerate (Phases 3-4)",
            "phase_alignment": [3, 4],
            "goal": "Upgrade to adaptive pre-merge intelligence with strong governance feedback.",
            "priority": "P1",
            "depends_on": ["impact-lock-phases-1-2"],
            "owner_hint": "release-platform",
            "actions": [
                "Run `python -m sdetkit checks run --profile strict --format json` in PR workflows.",
                "Publish strict verdict JSON + markdown for every PR as traceable evidence.",
                "Track fail trends weekly and assign remediation owner in the same sprint.",
            ],
            "success_signal": "strict pre-merge contracts are deterministic and auditable",
            "evidence": {
                "gate_fast_ok": _status(gate_fast),
                "doctor_ok": _status(doctor),
            },
        },
        {
            "id": "impact-prove-phases-5-6",
            "name": "Impact Prove (Phases 5-6)",
            "phase_alignment": [5, 6],
            "goal": "Prove whole-repo reliability with trend observability and final system run.",
            "priority": "P1",
            "depends_on": ["impact-accelerate-phases-3-4"],
            "owner_hint": "devx-observability",
            "actions": [
                "Run nightly `python scripts/build_top_tier_reporting_bundle.py` for trend intelligence.",
                "Alert on negative KPI drift from generated `docs/artifacts/*summary*.json` data.",
                f"Raise coverage to strict fail-under {strict_cov if strict_cov is not None else 95} for final release truth.",
                "Execute full-system validation run before ship/no-ship decision.",
            ],
            "success_signal": "phase 1-6 evidence rolls up into one reliable release verdict",
            "evidence": {"coverage_strict": strict_cov, "doctor_score": doctor.get("score")},
        },
    ]

    return {
        "schema_version": "sdetkit.impact-workflow-map.v1",
        "current_state": {
            "gate_fast_ok": _status(gate_fast),
            "gate_release_ok": _status(gate_release),
            "doctor_ok": _status(doctor),
            "doctor_score": doctor.get("score"),
        },
        "impact_workflow": {"step_1": steps[0], "step_2": steps[1], "step_3": steps[2]},
    }


def _render_markdown(plan: dict[str, object]) -> str:
    state = plan["current_state"]
    workflow = plan["impact_workflow"]
    lines = [
        "# Impact Workflow Map",
        "",
        "## Current State",
        f"- gate fast ok: `{state['gate_fast_ok']}`",
        f"- gate release ok: `{state['gate_release_ok']}`",
        f"- doctor ok: `{state['doctor_ok']}` (score: `{state['doctor_score']}`)",
        "",
        "## 3-Step Impact Workflow",
    ]

    for key in ("step_1", "step_2", "step_3"):
        step = workflow[key]
        lines.append(f"### {step['id']}: {step['name']}")
        lines.append(f"- Phase alignment: `{step['phase_alignment']}`")
        lines.append(f"- Priority: **{step['priority']}**")
        lines.append(f"- Goal: {step['goal']}")
        lines.append(f"- Success signal: {step['success_signal']}")
        for action in step["actions"]:
            lines.append(f"- [ ] {action}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a 3-step impact workflow map aligned to phases 1-6."
    )
    parser.add_argument("--gate-fast", default="build/gate-fast.json")
    parser.add_argument("--gate-release", default="build/release-preflight.json")
    parser.add_argument("--doctor", default="build/doctor.json")
    parser.add_argument("--quality-script", default="quality.sh")
    parser.add_argument("--out-json", default="build/impact-workflow-map.json")
    parser.add_argument("--out-md", default="build/impact-workflow-map.md")
    args = parser.parse_args(argv)

    try:
        gate_fast = _load_json(Path(args.gate_fast))
        gate_release = _load_json(Path(args.gate_release))
        doctor = _load_json(Path(args.doctor))
        quality_text = Path(args.quality_script).read_text(encoding="utf-8")
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"impact workflow map failed: {exc}", file=sys.stderr)
        return 1

    plan = build_impact_workflow(gate_fast, gate_release, doctor, quality_text)

    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    out_md.write_text(_render_markdown(plan), encoding="utf-8")
    print(f"wrote impact workflow map: {out_json} and {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
