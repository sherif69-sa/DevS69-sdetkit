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
    "weekly-review-lane": "sdetkit.weekly_review_28",
    "phase1-hardening": "sdetkit.phase1_hardening_29",
    "phase1-wrap": "sdetkit.phase1_wrap_30",
    "phase2-kickoff": "sdetkit.phase2_kickoff_31",
    "release-cadence": "sdetkit.release_cadence_32",
    "demo-asset": "sdetkit.demo_asset_33",
    "demo-asset2": "sdetkit.demo_asset2_34",
    "kpi-instrumentation": "sdetkit.kpi_instrumentation_35",
    "distribution-closeout": "sdetkit.distribution_closeout_36",
    "experiment-lane": "sdetkit.experiment_lane_37",
    "distribution-batch": "sdetkit.distribution_batch_38",
    "playbook-post": "sdetkit.playbook_post_39",
    "scale-lane": "sdetkit.scale_lane_40",
    "expansion-automation": "sdetkit.expansion_automation_41",
    "optimization-closeout-foundation": "sdetkit.optimization_closeout_42",
}
