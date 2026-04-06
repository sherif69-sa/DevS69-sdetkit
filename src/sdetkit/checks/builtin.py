from __future__ import annotations

import shutil
import subprocess
import time
from collections.abc import Callable
from typing import Literal

from .base import CheckContext, CheckDefinition
from .results import CheckRecord


def _stringify_command(command: tuple[str, ...]) -> str:
    return " ".join(command)


def _existing_evidence(ctx: CheckContext, outputs: tuple[str, ...]) -> tuple[str, ...]:
    evidence: list[str] = []
    for rel in outputs:
        candidate = ctx.resolve(rel)
        if candidate.exists():
            evidence.append(str(candidate.relative_to(ctx.repo_root)))
    return tuple(evidence)


def _run_subprocess(
    check: CheckDefinition,
    ctx: CheckContext,
    command: tuple[str, ...],
    *,
    advisory: tuple[str, ...] = (),
) -> CheckRecord:
    ctx.out_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    log_path = ctx.out_dir / f"check.{check.id}.log"
    max_attempts = 2 if check.id == "tests_full" else 1
    attempt = 0
    proc: subprocess.CompletedProcess[str] | None = None
    outputs: list[str] = []
    while attempt < max_attempts:
        attempt += 1
        current = subprocess.run(
            command,
            cwd=ctx.repo_root,
            env=dict(ctx.env),
            text=True,
            capture_output=True,
            check=False,
        )
        outputs.append(f"--- attempt {attempt}/{max_attempts} ---\n")
        outputs.append(current.stdout)
        outputs.append(current.stderr)
        proc = current
        if current.returncode == 0:
            break
    elapsed = time.monotonic() - started
    assert proc is not None
    combined = "".join(outputs)
    log_path.write_text(combined, encoding="utf-8")
    status: Literal["passed", "failed"]
    if proc.returncode == 0:
        status = "passed"
    else:
        status = "failed"
    reason = "" if proc.returncode == 0 else f"command failed (rc={proc.returncode})"
    evidence_paths = _existing_evidence(ctx, check.evidence_outputs)
    metadata = {
        "returncode": proc.returncode,
        "attempts": attempt,
        "max_attempts": max_attempts,
        "category": check.category,
        "truth_level": check.truth_level,
        "target_mode": ctx.target_mode,
        "target_reason": ctx.target_reason,
        "changed_paths": list(ctx.changed_paths),
        "selected_targets": list(ctx.selected_targets),
        "cache": {"status": "fresh"},
    }
    return CheckRecord(
        id=check.id,
        title=check.title,
        status=status,
        blocking=not check.advisory_only,
        reason=reason,
        command=_stringify_command(command),
        advisory=advisory,
        log_path=str(log_path.relative_to(ctx.repo_root)),
        evidence_paths=evidence_paths,
        elapsed_seconds=round(elapsed, 3),
        metadata=metadata,
    )


def _skip_missing_prereqs(check: CheckDefinition, ctx: CheckContext) -> CheckRecord | None:
    missing_tools = [tool for tool in check.required_tools if shutil.which(tool) is None]
    if missing_tools:
        return CheckRecord(
            id=check.id,
            title=check.title,
            status="skipped",
            blocking=not check.advisory_only,
            reason=f"missing required tool(s): {', '.join(sorted(missing_tools))}",
            command=_stringify_command(check.command),
            advisory=("planner skipped a check with unavailable tools",),
            metadata={
                "category": check.category,
                "truth_level": check.truth_level,
                "target_mode": ctx.target_mode,
                "target_reason": ctx.target_reason,
                "changed_paths": list(ctx.changed_paths),
                "selected_targets": list(ctx.selected_targets),
                "cache": {"status": "not-applicable"},
            },
        )

    missing_paths = [path for path in check.required_paths if not ctx.resolve(path).exists()]
    if missing_paths:
        return CheckRecord(
            id=check.id,
            title=check.title,
            status="skipped",
            blocking=not check.advisory_only,
            reason=f"missing required path(s): {', '.join(sorted(missing_paths))}",
            command=_stringify_command(check.command),
            advisory=("planner skipped a check with missing required paths",),
            metadata={
                "category": check.category,
                "truth_level": check.truth_level,
                "target_mode": ctx.target_mode,
                "target_reason": ctx.target_reason,
                "changed_paths": list(ctx.changed_paths),
                "selected_targets": list(ctx.selected_targets),
                "cache": {"status": "not-applicable"},
            },
        )
    return None


def _make_command_runner(
    command_factory: Callable[[CheckContext], tuple[str, ...]],
    *,
    advisory: tuple[str, ...] = (),
):
    def _runner(check: CheckDefinition, ctx: CheckContext) -> CheckRecord:
        skipped = _skip_missing_prereqs(check, ctx)
        if skipped is not None:
            return skipped
        return _run_subprocess(check, ctx, command_factory(ctx), advisory=advisory)

    return _runner


def _repo_layout_command(ctx: CheckContext) -> tuple[str, ...]:
    return (ctx.python_executable, "scripts/check_repo_layout.py")


def _format_check_command(ctx: CheckContext) -> tuple[str, ...]:
    return (ctx.python_executable, "-m", "ruff", "format", "--check", ".")


def _lint_command(ctx: CheckContext) -> tuple[str, ...]:
    return (ctx.python_executable, "-m", "ruff", "check", ".")


def _typing_command(ctx: CheckContext) -> tuple[str, ...]:
    return (ctx.python_executable, "-m", "mypy", "--config-file", "pyproject.toml", "src")


def _tests_smoke_command(ctx: CheckContext) -> tuple[str, ...]:
    if ctx.target_mode == "targeted" and ctx.selected_targets:
        return (
            ctx.python_executable,
            "-m",
            "pytest",
            "-q",
            "-o",
            "addopts=",
            *ctx.selected_targets,
        )
    return (ctx.python_executable, "-m", "sdetkit", "gate", "fast")


def _tests_full_command(ctx: CheckContext) -> tuple[str, ...]:
    if ctx.target_mode == "targeted" and ctx.selected_targets:
        return (
            ctx.python_executable,
            "-m",
            "pytest",
            "-q",
            "-o",
            "addopts=",
            *ctx.selected_targets,
        )
    return (ctx.python_executable, "-m", "pytest", "-q", "-o", "addopts=")


def _feature_registry_contract_command(ctx: CheckContext) -> tuple[str, ...]:
    return (ctx.python_executable, "scripts/check_feature_registry_contract.py")


def _doctor_core_command(ctx: CheckContext) -> tuple[str, ...]:
    return (
        ctx.python_executable,
        "-m",
        "sdetkit",
        "doctor",
        "--dev",
        "--ci",
        "--deps",
        "--repo",
        "--upgrade-audit",
        "--format",
        "json",
        "--out",
        str(ctx.artifact_path("doctor.json")),
    )


def _security_scan_command(ctx: CheckContext) -> tuple[str, ...]:
    return (
        ctx.python_executable,
        "-m",
        "sdetkit",
        "security",
        "scan",
        "--fail-on",
        "none",
        "--format",
        "sarif",
        "--output",
        str(ctx.artifact_path("security.sarif")),
        "--sbom-output",
        str(ctx.artifact_path("security.sbom.json")),
    )


def _bind(
    check: CheckDefinition, runner_factory: Callable[[CheckDefinition, CheckContext], CheckRecord]
) -> CheckDefinition:
    return CheckDefinition(
        **{**check.__dict__, "run": lambda ctx, _check=check: runner_factory(_check, ctx)}
    )


BUILTIN_CHECKS: tuple[CheckDefinition, ...] = (
    _bind(
        CheckDefinition(
            id="repo_layout",
            title="Repository layout contract",
            category="repo",
            cost="cheap",
            truth_level="smoke",
            required_tools=("python3",),
            required_paths=("scripts/check_repo_layout.py",),
            command=("python3", "scripts/check_repo_layout.py"),
            evidence_outputs=(),
            notes="Protects baseline repo structure before deeper checks run.",
        ),
        _make_command_runner(_repo_layout_command),
    ),
    _bind(
        CheckDefinition(
            id="feature_registry_contract",
            title="Feature registry contract",
            category="repo",
            cost="cheap",
            truth_level="smoke",
            required_tools=("python",),
            required_paths=(
                "scripts/check_feature_registry_contract.py",
                "src/sdetkit/data/feature_registry.json",
            ),
            command=("python", "scripts/check_feature_registry_contract.py"),
            notes="Ensures Tier-mapped commands keep valid docs/tests linkage and contract fields.",
        ),
        _make_command_runner(_feature_registry_contract_command),
    ),
    _bind(
        CheckDefinition(
            id="format_check",
            title="Ruff format check",
            category="format",
            cost="cheap",
            truth_level="standard",
            required_tools=("ruff",),
            command=("python", "-m", "ruff", "format", "--check", "."),
        ),
        _make_command_runner(_format_check_command),
    ),
    _bind(
        CheckDefinition(
            id="lint",
            title="Ruff lint",
            category="lint",
            cost="cheap",
            truth_level="standard",
            required_tools=("ruff",),
            command=("python", "-m", "ruff", "check", "."),
        ),
        _make_command_runner(_lint_command),
    ),
    _bind(
        CheckDefinition(
            id="typing",
            title="Mypy typing",
            category="typing",
            cost="moderate",
            truth_level="standard",
            required_tools=("mypy",),
            required_paths=("pyproject.toml", "src"),
            command=("python", "-m", "mypy", "--config-file", "pyproject.toml", "src"),
        ),
        _make_command_runner(_typing_command),
    ),
    _bind(
        CheckDefinition(
            id="tests_smoke",
            title="Fast/smoke tests",
            category="tests",
            cost="moderate",
            truth_level="smoke",
            parallel_safe=False,
            required_tools=("pytest",),
            command=("python", "-m", "sdetkit", "gate", "fast"),
            evidence_outputs=(".sdetkit/gate.fast.snapshot.json",),
            notes="Useful for local confidence only; never represents merge truth.",
        ),
        _make_command_runner(
            _tests_smoke_command,
            advisory=("smoke gate is not merge/release truth",),
        ),
    ),
    _bind(
        CheckDefinition(
            id="tests_full",
            title="Full pytest suite",
            category="tests",
            cost="expensive",
            truth_level="merge",
            dependencies=("format_check", "lint", "typing"),
            parallel_safe=False,
            required_tools=("pytest",),
            command=("python", "-m", "pytest", "-q", "-o", "addopts="),
            notes="This is the full truth path for merge and release verification.",
        ),
        _make_command_runner(_tests_full_command),
    ),
    _bind(
        CheckDefinition(
            id="doctor_core",
            title="Doctor core report",
            category="doctor",
            cost="moderate",
            truth_level="standard",
            required_tools=("python",),
            command=(
                "python",
                "-m",
                "sdetkit",
                "doctor",
                "--dev",
                "--ci",
                "--deps",
                "--repo",
                "--upgrade-audit",
                "--format",
                "json",
            ),
            evidence_outputs=(".sdetkit/out/doctor.json",),
        ),
        _make_command_runner(_doctor_core_command),
    ),
    _bind(
        CheckDefinition(
            id="security_source_scan",
            title="Security source scan",
            category="security",
            cost="moderate",
            truth_level="standard",
            required_tools=("python",),
            command=(
                "python",
                "-m",
                "sdetkit",
                "security",
                "scan",
                "--fail-on",
                "none",
                "--format",
                "sarif",
            ),
            evidence_outputs=(".sdetkit/out/security.sarif", ".sdetkit/out/security.sbom.json"),
            advisory_only=True,
            notes="Generated and noisy paths remain excluded by the existing security tooling.",
        ),
        _make_command_runner(_security_scan_command),
    ),
)
