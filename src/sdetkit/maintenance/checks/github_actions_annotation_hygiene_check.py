from __future__ import annotations

from pathlib import Path

from sdetkit import github_actions_annotation_hygiene

from ..types import CheckAction, CheckResult, MaintenanceContext

CHECK_NAME = "github_actions_annotation_hygiene"
CHECK_MODES = {"quick", "full"}
ENV_LOG_PATH = "SDETKIT_GITHUB_ACTIONS_ANNOTATION_LOG"


def _log_path(ctx: MaintenanceContext) -> Path | None:
    raw = str(ctx.env.get(ENV_LOG_PATH, "")).strip()
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_absolute() else ctx.repo_root / path


def _actions_for_payload(payload: dict) -> list[CheckAction]:
    actions = [
        CheckAction(
            id="annotation-hygiene-input",
            title="Provide GitHub Actions annotation log",
            applied=False,
            notes=f"Set {ENV_LOG_PATH} to a saved annotations log path.",
        )
    ]
    findings = payload.get("findings", [])
    if not isinstance(findings, list):
        return actions

    for finding in findings[:5]:
        if not isinstance(finding, dict):
            continue
        finding_id = str(finding.get("id", "annotation-hygiene-follow-up"))
        title = str(finding.get("recommendation", "")).strip()
        if not title:
            title = str(finding.get("title", "Inspect GitHub Actions annotation")).strip()
        actions.append(
            CheckAction(
                id=finding_id,
                title=title,
                applied=False,
                notes=str(finding.get("severity", "info")),
            )
        )
    return actions


def run(ctx: MaintenanceContext) -> CheckResult:
    path = _log_path(ctx)
    if path is None:
        return CheckResult(
            ok=True,
            summary="GitHub Actions annotation hygiene log not configured",
            details={
                "configured": False,
                "env_var": ENV_LOG_PATH,
            },
            actions=[
                CheckAction(
                    id="annotation-hygiene-configure",
                    title="Capture GitHub Actions annotations before running this check",
                    applied=False,
                    notes=f"Set {ENV_LOG_PATH} to a saved annotation log file.",
                )
            ],
        )

    if not path.exists():
        return CheckResult(
            ok=False,
            summary="GitHub Actions annotation hygiene log was not found",
            details={
                "configured": True,
                "env_var": ENV_LOG_PATH,
                "path": path.as_posix(),
            },
            actions=[
                CheckAction(
                    id="annotation-hygiene-missing-log",
                    title="Write or download the GitHub Actions annotation log",
                    applied=False,
                    notes=path.as_posix(),
                )
            ],
        )

    payload = github_actions_annotation_hygiene.analyze_file(path)
    findings = int(payload.get("finding_count", 0) or 0)
    warnings = int(payload.get("warning_count", 0) or 0)
    notices = int(payload.get("notice_count", 0) or 0)
    summary = (
        f"GitHub Actions annotation hygiene: {findings} finding(s), "
        f"{warnings} warning(s), {notices} notice(s)"
    )

    return CheckResult(
        ok=bool(payload.get("ok", False)),
        summary=summary,
        details={
            "configured": True,
            "env_var": ENV_LOG_PATH,
            "path": path.as_posix(),
            "annotation_hygiene": payload,
        },
        actions=_actions_for_payload(payload),
    )


__all__ = ["run", "CHECK_NAME", "CHECK_MODES"]
