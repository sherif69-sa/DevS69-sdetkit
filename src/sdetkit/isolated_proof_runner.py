from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sdetkit.git_inventory_collector import (
    BASE_HEAD,
    STAGED_WORKTREE,
    collect_git_inventory,
)
from sdetkit.network_boundary import (
    NETWORK_ISOLATION_ENFORCED,
    NETWORK_ISOLATION_REQUIRED,
    PROOF_EXECUTION_ALLOWED,
    assess_network_boundary,
)

SCHEMA_VERSION = "sdetkit.isolated_proof_runner.v3"
DEFAULT_OUT_DIR = Path("build") / "isolated-proof-runner"
EVIDENCE_JSON = "verification-evidence.json"
EVIDENCE_MD = "verification-evidence.md"
DEFAULT_TIMEOUT_SECONDS = 120
MAX_CAPTURE_CHARS = 8000

JsonObject = dict[str, Any]

WORKSPACE_MUTATED_DURING_EXECUTION = "_".join(("workspace", "mutated", "during", "execution"))
CLAIMED_CHANGED_FILES = "_".join(("claimed", "changed", "files"))
INVENTORY_CLAIM_MATCH = "_".join(("inventory", "claim", "match"))

IGNORED_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "htmlcov",
}
IGNORED_FILES = {
    ".coverage",
    "coverage.xml",
}


@dataclass(frozen=True)
class ProofProfile:
    profile_id: str
    canonical_command: str
    argv_suffix: tuple[str, ...]


PROOF_PROFILES = {
    "pre_commit_all": ProofProfile(
        profile_id="pre_commit_all",
        canonical_command="python -m pre_commit run -a",
        argv_suffix=("-m", "pre_commit", "run", "-a"),
    ),
    "ruff_src_tests": ProofProfile(
        profile_id="ruff_src_tests",
        canonical_command="python -m ruff check src tests",
        argv_suffix=("-m", "ruff", "check", "src", "tests"),
    ),
    "mypy_src": ProofProfile(
        profile_id="mypy_src",
        canonical_command="python -m mypy src",
        argv_suffix=("-m", "mypy", "src"),
    ),
}


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes"}


def _int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _string_list(value: Any) -> list[str]:
    return sorted({_string(item) for item in _as_list(value) if _string(item)})


def _capture_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        rendered = value.decode("utf-8", errors="replace")
    else:
        rendered = value
    if len(rendered) <= MAX_CAPTURE_CHARS:
        return rendered
    return rendered[:MAX_CAPTURE_CHARS] + "\n... output truncated ...\n"


def _ignored_relative_path(relative: Path) -> bool:
    return any(part in IGNORED_NAMES for part in relative.parts) or relative.name in IGNORED_FILES


def _copy_ignore(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name in IGNORED_NAMES or name in IGNORED_FILES}


def _snapshot_workspace(workspace: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for path in sorted(workspace.rglob("*")):
        relative = path.relative_to(workspace)
        if _ignored_relative_path(relative) or path.is_dir():
            continue

        digest = hashlib.sha256()
        if path.is_symlink():
            digest.update(os.readlink(path).encode("utf-8", errors="replace"))
        else:
            digest.update(path.read_bytes())
        snapshot[relative.as_posix()] = digest.hexdigest()
    return snapshot


def _changed_paths(before: Mapping[str, str], after: Mapping[str, str]) -> list[str]:
    paths = set(before) | set(after)
    return sorted(path for path in paths if before.get(path) != after.get(path))


def _execution_environment() -> dict[str, str]:
    allowed_keys = {
        "CI",
        "HOME",
        "PATH",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "TMPDIR",
        "USERPROFILE",
        "VIRTUAL_ENV",
    }
    environment = {key: value for key, value in os.environ.items() if key in allowed_keys}
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONNOUSERSITE"] = "1"
    return environment


def _run_setup_command(
    argv: list[str],
    *,
    cwd: Path,
    environment: Mapping[str, str],
) -> None:
    completed = subprocess.run(
        argv,
        cwd=cwd,
        env=dict(environment),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        shell=False,
    )
    if completed.returncode != 0:
        message = _capture_text(completed.stderr or completed.stdout)
        raise RuntimeError(f"isolated workspace setup failed: {message}")


def _prepare_isolated_workspace(source_root: Path, workspace: Path) -> None:
    shutil.copytree(
        source_root,
        workspace,
        symlinks=True,
        ignore=_copy_ignore,
    )

    environment = _execution_environment()
    _run_setup_command(["git", "init", "--quiet"], cwd=workspace, environment=environment)
    _run_setup_command(["git", "add", "-A"], cwd=workspace, environment=environment)
    _run_setup_command(
        [
            "git",
            "-c",
            "user.name=SDETKit Proof Runner",
            "-c",
            "user.email=proof-runner@invalid.local",
            "commit",
            "--quiet",
            "--no-verify",
            "-m",
            "isolated proof baseline",
        ],
        cwd=workspace,
        environment=environment,
    )


def _profile_result(
    *,
    profile: ProofProfile,
    workspace: Path,
    timeout_seconds: int,
) -> JsonObject:
    before = _snapshot_workspace(workspace)
    argv = [sys.executable, *profile.argv_suffix]

    try:
        completed = subprocess.run(
            argv,
            cwd=workspace,
            env=_execution_environment(),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            shell=False,
        )
        exit_code = completed.returncode
        timed_out = False
        stdout = _capture_text(completed.stdout)
        stderr = _capture_text(completed.stderr)
    except subprocess.TimeoutExpired as exc:
        exit_code = -1
        timed_out = True
        stdout = _capture_text(exc.stdout)
        stderr = _capture_text(exc.stderr)

    after = _snapshot_workspace(workspace)
    mutated_files = _changed_paths(before, after)
    workspace_mutated = bool(mutated_files)

    status = "passed" if exit_code == 0 and not timed_out and not workspace_mutated else "failed"

    return {
        "profile_id": profile.profile_id,
        "command": profile.canonical_command,
        "argv_display": ["python", *profile.argv_suffix],
        "status": status,
        "exit_code": exit_code,
        "timed_out": timed_out,
        WORKSPACE_MUTATED_DURING_EXECUTION: workspace_mutated,
        "workspace_mutated_files": mutated_files,
        "stdout": stdout,
        "stderr": stderr,
    }


def run_isolated_proof(
    *,
    repo_root: Path,
    changed_files: list[str],
    profile_ids: list[str],
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    inventory_mode: str | None = None,
    base_ref: str = "",
    head_ref: str = "HEAD",
    require_network_isolation: bool = False,
) -> JsonObject:
    if timeout_seconds < 1:
        raise ValueError("timeout_seconds must be at least 1")

    source_root = repo_root.resolve()
    if not source_root.exists() or not source_root.is_dir():
        msg = f"repo_root does not exist or is not a directory: {source_root}"
        raise ValueError(msg)

    if not profile_ids:
        raise ValueError("at least one proof profile is required")

    unknown_profiles = sorted(set(profile_ids) - set(PROOF_PROFILES))
    if unknown_profiles:
        msg = f"unsupported proof profile: {', '.join(unknown_profiles)}"
        raise ValueError(msg)

    claimed_changed_files = sorted(set(changed_files))
    inventory: JsonObject = {}
    effective_changed_files = claimed_changed_files
    changed_files_source = "caller_supplied_inventory_unverified"
    inventory_claim_match: bool | None = None
    git_inventory_verified = False
    network_boundary = assess_network_boundary(
        require_network_isolation=require_network_isolation,
    )
    proof_execution_allowed = _bool(network_boundary.get(PROOF_EXECUTION_ALLOWED))

    if inventory_mode:
        inventory = collect_git_inventory(
            repo_root=source_root,
            mode=inventory_mode,
            base_ref=base_ref,
            head_ref=head_ref,
        )
        effective_changed_files = _string_list(inventory.get("changed_files"))
        changed_files_source = _string(inventory.get("changed_files_source"))
        inventory_claim_match = (
            not claimed_changed_files or claimed_changed_files == effective_changed_files
        )
        git_inventory_verified = (
            _bool(inventory.get("git_inventory_verified")) and inventory_claim_match
        )

    requested_profiles = list(dict.fromkeys(profile_ids))
    results: list[JsonObject] = []

    if proof_execution_allowed:
        with tempfile.TemporaryDirectory(prefix="sdetkit-proof-") as temp_dir:
            workspace = Path(temp_dir) / "workspace"
            _prepare_isolated_workspace(source_root, workspace)

            for profile_id in requested_profiles:
                results.append(
                    _profile_result(
                        profile=PROOF_PROFILES[profile_id],
                        workspace=workspace,
                        timeout_seconds=timeout_seconds,
                    )
                )

    passed_count = sum(1 for result in results if result["status"] == "passed")
    failed_count = len(results) - passed_count
    blocked_count = 0 if proof_execution_allowed else len(requested_profiles)
    inventory_failed = inventory_claim_match is False
    status = (
        "passed"
        if proof_execution_allowed and failed_count == 0 and not inventory_failed
        else "failed"
    )

    if not proof_execution_allowed:
        boundary_reason = (
            "Network-isolated proof was required, but no verified runtime "
            "containment backend is available; proof execution was blocked."
        )
    elif not inventory_mode:
        boundary_reason = (
            "The runner executes allowlisted proof profiles in an isolated copy, "
            "but changed-file inventory is not yet git-derived."
        )
    elif inventory_failed:
        boundary_reason = (
            "Git-derived inventory disagrees with the caller-declared changed-file claim; "
            "verification evidence is blocked."
        )
    else:
        boundary_reason = (
            "The runner executes allowlisted proof profiles in an isolated copy "
            "with Git-derived changed-file inventory; automation remains disabled."
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "changed_files": effective_changed_files,
        CLAIMED_CHANGED_FILES: claimed_changed_files,
        "changed_files_source": changed_files_source,
        INVENTORY_CLAIM_MATCH: inventory_claim_match,
        "git_inventory": inventory,
        "network_boundary": network_boundary,
        "requested_profiles": requested_profiles,
        "proof_results": results,
        "proof_summary": {
            "requested_count": len(requested_profiles),
            "executed_count": len(results),
            "blocked_count": blocked_count,
            "passed_count": passed_count,
            "failed_count": failed_count,
        },
        "isolation": {
            "mode": "temporary_workspace_copy",
            "shell_enabled": False,
            "allowlisted_profiles_only": True,
            "timeout_seconds": timeout_seconds,
            "source_workspace_used_as_command_cwd": False,
            NETWORK_ISOLATION_REQUIRED: _bool(network_boundary.get(NETWORK_ISOLATION_REQUIRED)),
            NETWORK_ISOLATION_ENFORCED: _bool(network_boundary.get(NETWORK_ISOLATION_ENFORCED)),
            "network_boundary_status": _string(network_boundary.get("status")),
            "network_boundary_backend": _string(network_boundary.get("backend")),
            "proof_execution_blocked": not proof_execution_allowed,
        },
        "decision_boundary": {
            "git_inventory_verified": git_inventory_verified,
            "network_isolation_verified": _bool(network_boundary.get(NETWORK_ISOLATION_ENFORCED)),
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
            "reason": boundary_reason,
        },
    }


def render_markdown(evidence: Mapping[str, Any]) -> str:
    summary = _as_dict(evidence.get("proof_summary"))
    isolation = _as_dict(evidence.get("isolation"))
    boundary = _as_dict(evidence.get("decision_boundary"))
    inventory = _as_dict(evidence.get("git_inventory"))
    network_boundary = _as_dict(evidence.get("network_boundary"))
    results = [_as_dict(item) for item in _as_list(evidence.get("proof_results"))]
    claim_value = evidence.get(INVENTORY_CLAIM_MATCH)
    claim_status = "not_checked" if claim_value is None else str(_bool(claim_value)).lower()

    lines = [
        "# Isolated proof runner evidence",
        "",
        f"- Schema: `{_string(evidence.get('schema_version'))}`",
        f"- Status: `{_string(evidence.get('status'))}`",
        f"- Profiles requested: `{_int(summary.get('requested_count'))}`",
        f"- Profiles executed: `{_int(summary.get('executed_count'))}`",
        f"- Profiles blocked: `{_int(summary.get('blocked_count'))}`",
        f"- Profiles passed: `{_int(summary.get('passed_count'))}`",
        f"- Profiles failed: `{_int(summary.get('failed_count'))}`",
        f"- Changed-files source: `{_string(evidence.get('changed_files_source'))}`",
        f"- Inventory claim matches: `{claim_status}`",
        f"- Git inventory mode: `{_string(inventory.get('mode') or 'not_used')}`",
        "",
        "## Execution isolation",
        "",
        f"- Mode: `{_string(isolation.get('mode'))}`",
        f"- Shell enabled: `{str(_bool(isolation.get('shell_enabled'))).lower()}`",
        (
            "- Allowlisted profiles only: "
            f"`{str(_bool(isolation.get('allowlisted_profiles_only'))).lower()}`"
        ),
        (
            "- Source workspace used as command cwd: "
            f"`{str(_bool(isolation.get('source_workspace_used_as_command_cwd'))).lower()}`"
        ),
        (
            "- Network isolation required: "
            f"`{str(_bool(isolation.get(NETWORK_ISOLATION_REQUIRED))).lower()}`"
        ),
        (
            "- Network isolation enforced: "
            f"`{str(_bool(isolation.get(NETWORK_ISOLATION_ENFORCED))).lower()}`"
        ),
        f"- Network boundary status: `{_string(network_boundary.get('status'))}`",
        (
            "- Proof execution blocked: "
            f"`{str(_bool(isolation.get('proof_execution_blocked'))).lower()}`"
        ),
        "",
        "## Proof results",
        "",
    ]

    if results:
        for result in results:
            lines.append(
                f"- `{_string(result.get('profile_id'))}`: "
                f"status=`{_string(result.get('status'))}`, "
                f"exit_code=`{_int(result.get('exit_code'), default=-1)}`, "
                "workspace_mutated=`"
                f"{str(_bool(result.get(WORKSPACE_MUTATED_DURING_EXECUTION))).lower()}`"
            )
            lines.append(f"  - Command: `{_string(result.get('command'))}`")
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Boundary",
            "",
            (
                "- Git-derived file inventory verified: "
                f"`{str(_bool(boundary.get('git_inventory_verified'))).lower()}`"
            ),
            f"- Automation allowed: `{str(_bool(boundary.get('automation_allowed'))).lower()}`",
            f"- Merge authorized: `{str(_bool(boundary.get('merge_authorized'))).lower()}`",
            (
                "- Semantic equivalence proven: "
                f"`{str(_bool(boundary.get('semantic_equivalence_proven'))).lower()}`"
            ),
            "- This runner does not accept arbitrary command strings.",
            "- Git-derived inventory is used only when explicitly requested and collected in-process.",
            "",
        ]
    )
    return "\n".join(lines)


def write_evidence(evidence: Mapping[str, Any], *, out_dir: Path) -> dict[str, str]:
    json_path = out_dir / EVIDENCE_JSON
    markdown_path = out_dir / EVIDENCE_MD
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(evidence), encoding="utf-8")
    return {
        "verification_evidence_json": json_path.as_posix(),
        "verification_evidence_markdown": markdown_path.as_posix(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.isolated_proof_runner")
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--changed-file", action="append", default=[])
    parser.add_argument("--inventory-mode", choices=[BASE_HEAD, STAGED_WORKTREE])
    parser.add_argument("--base-ref", default="")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--require-network-isolation", action="store_true")
    parser.add_argument(
        "--profile",
        action="append",
        choices=sorted(PROOF_PROFILES),
        required=True,
    )
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        evidence = run_isolated_proof(
            repo_root=args.repo_root,
            changed_files=args.changed_file,
            profile_ids=args.profile,
            timeout_seconds=args.timeout_seconds,
            inventory_mode=args.inventory_mode,
            base_ref=args.base_ref,
            head_ref=args.head_ref,
            require_network_isolation=args.require_network_isolation,
        )
        artifacts = write_evidence(evidence, out_dir=args.out_dir)
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        print(f"error={exc}")
        return 2

    if args.format == "json":
        print(
            json.dumps(
                {
                    "status": evidence["status"],
                    "artifacts": artifacts,
                    "proof_summary": evidence["proof_summary"],
                    "decision_boundary": evidence["decision_boundary"],
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        for key, value in artifacts.items():
            print(f"{key}: {value}")

    return 0 if evidence["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
