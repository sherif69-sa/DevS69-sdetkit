from __future__ import annotations

LEGACY_NAMESPACE_COMMANDS: tuple[str, ...] = (
    "weekly-review-lane",
    "phase1-hardening",
    "phase1-wrap",
    "phase2-kickoff",
    "release-cadence",
    "demo-asset",
    "demo-asset2",
    "kpi-instrumentation",
    "experiment-lane",
    "distribution-batch",
    "playbook-post",
    "scale-lane",
    "expansion-automation",
    "optimization-closeout-foundation",
)

LEGACY_FOUNDATION_COMMAND_MODULES: dict[str, str] = {
    "weekly-review-lane": "sdetkit.weekly_review_foundation",
    "phase1-hardening": "sdetkit.phase1_hardening",
    "phase1-wrap": "sdetkit.phase1_wrap",
    "phase2-kickoff": "sdetkit.phase2_kickoff",
    "release-cadence": "sdetkit.release_cadence",
    "demo-asset": "sdetkit.demo_asset",
    "demo-asset2": "sdetkit.demo_asset2",
    "kpi-instrumentation": "sdetkit.kpi_instrumentation",
    "distribution-closeout": "sdetkit.distribution",
    "experiment-lane": "sdetkit.experiment_workflow",
    "distribution-batch": "sdetkit.distribution_batch",
    "playbook-post": "sdetkit.playbook_post",
    "scale-lane": "sdetkit.scale_workflow",
    "expansion-automation": "sdetkit.expansion_automation",
    "optimization-closeout-foundation": "sdetkit.optimization_foundation",
}
