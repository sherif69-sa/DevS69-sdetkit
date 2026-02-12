from __future__ import annotations

from ..types import CheckAction, CheckResult, MaintenanceContext

CHECK_NAME = "custom_example_check"


def run(ctx: MaintenanceContext) -> CheckResult:
    return CheckResult(
        ok=True,
        summary="example extension check loaded",
        details={
            "message": "Drop a new module in sdetkit/maintenance/checks with CHECK_NAME and run(ctx).",
            "mode": ctx.mode,
        },
        actions=[
            CheckAction(
                id="customize-check",
                title="Create project-specific checks",
                applied=False,
                notes="Use this file as a template for new check modules",
            )
        ],
    )


CHECK_MODES = {"quick", "full"}
