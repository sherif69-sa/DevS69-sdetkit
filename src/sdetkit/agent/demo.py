from __future__ import annotations

from pathlib import Path

from .core import init_agent, run_agent
from .dashboard import build_dashboard
from .templates import run_template, template_by_id

_DEMO_SCENARIOS: dict[str, tuple[str, ...]] = {
    "repo-enterprise-audit": (
        "repo-health-audit",
        "security-governance-summary",
        "report-dashboard",
    )
}


def run_demo(*, root: Path, scenario: str) -> dict[str, object]:
    if scenario not in _DEMO_SCENARIOS:
        raise ValueError(f"unknown scenario '{scenario}'")

    created = init_agent(root, root / ".sdetkit/agent/config.yaml")
    template_outputs: list[dict[str, str]] = []

    for template_id in _DEMO_SCENARIOS[scenario]:
        template = template_by_id(root, template_id)
        output_dir = root / ".sdetkit" / "agent" / "demo" / template_id
        record = run_template(root, template=template, set_values={}, output_dir=output_dir)
        template_outputs.append(
            {
                "template": template_id,
                "status": str(record.get("status", "")),
                "output_dir": output_dir.as_posix(),
            }
        )
        run_agent(
            root,
            config_path=root / ".sdetkit/agent/config.yaml",
            task=f"template:{template_id}",
            auto_approve=True,
        )

    run_agent(
        root,
        config_path=root / ".sdetkit/agent/config.yaml",
        task='action fs.read {"path":"missing-enterprise-control.md"}',
        auto_approve=True,
    )

    dashboard_html = root / ".sdetkit" / "agent" / "demo" / "artifacts" / "agent-dashboard.html"
    dashboard_md = root / ".sdetkit" / "agent" / "demo" / "artifacts" / "agent-summary.md"
    dashboard_payload = build_dashboard(
        history_dir=root / ".sdetkit" / "agent" / "history",
        output=dashboard_html,
        fmt="html",
        summary_output=dashboard_md,
    )

    return {
        "status": "ok",
        "scenario": scenario,
        "created": created,
        "templates": template_outputs,
        "artifacts": {
            "dashboard_html": dashboard_payload["output"],
            "dashboard_md": dashboard_payload["markdown_summary"],
            "history_dir": (root / ".sdetkit" / "agent" / "history").as_posix(),
        },
    }
