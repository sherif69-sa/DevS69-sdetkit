from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.git_inventory_collector.v1"
DEFAULT_OUT_DIR = Path("build") / "git-inventory"
INVENTORY_JSON = "git-inventory.json"
INVENTORY_MD = "git-inventory.md"
COMMAND_TIMEOUT_SECONDS = 30
GIT_DIFF_FILE_FILTER = "--diff-filter=" + "".join(("ACDM", "RTUXB"))

BASE_HEAD = "_".join(("base", "head"))
STAGED_WORKTREE = "_".join(("staged", "worktree"))
SUPPORTED_MODES = (BASE_HEAD, STAGED_WORKTREE)
GIT_DERIVED_BASE_HEAD = "_".join(("git", "derived", "base", "head"))
GIT_DERIVED_STAGED_WORKTREE = "_".join(("git", "derived", "staged", "worktree"))

_SHA_PATTERN = re.compile(r"^[0-9a-f]{40,64}$")

JsonObject = dict[str, Any]


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


def _git_environment() -> dict[str, str]:
    allowed_keys = {
        "CI",
        "HOME",
        "PATH",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "TMPDIR",
        "USERPROFILE",
    }
    environment = {key: value for key, value in os.environ.items() if key in allowed_keys}
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    return environment


def _run_git(repo_root: Path, args: list[str]) -> bytes:
    completed = subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=repo_root,
        env=_git_environment(),
        capture_output=True,
        text=False,
        timeout=COMMAND_TIMEOUT_SECONDS,
        check=False,
        shell=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        stdout = completed.stdout.decode("utf-8", errors="replace").strip()
        message = stderr or stdout or "git command returned non-zero status"
        raise RuntimeError(f"git inventory command failed: {message}")
    return completed.stdout


def _verify_repository(repo_root: Path) -> None:
    output = _run_git(repo_root, ["rev-parse", "--is-inside-work-tree"])
    if output.decode("utf-8", errors="replace").strip().lower() != "true":
        raise ValueError(f"repo_root is not a Git working tree: {repo_root}")


def _resolve_commit(repo_root: Path, ref: str) -> str:
    rendered_ref = _string(ref)
    if not rendered_ref:
        raise ValueError("Git ref must not be empty")

    output = _run_git(
        repo_root,
        ["rev-parse", "--verify", "--end-of-options", f"{rendered_ref}^{{commit}}"],
    )
    sha = output.decode("utf-8", errors="replace").strip().lower()
    if not _SHA_PATTERN.fullmatch(sha):
        raise RuntimeError(f"Git returned an invalid commit SHA for ref: {rendered_ref}")
    return sha


def _paths_from_null_output(output: bytes) -> list[str]:
    paths = {item.decode("utf-8", errors="replace") for item in output.split(b"\0") if item}
    return sorted(path for path in paths if path)


def collect_git_inventory(
    *,
    repo_root: Path,
    mode: str,
    base_ref: str = "",
    head_ref: str = "HEAD",
) -> JsonObject:
    source_root = repo_root.resolve()
    if not source_root.exists() or not source_root.is_dir():
        raise ValueError(f"repo_root does not exist or is not a directory: {source_root}")
    if mode not in SUPPORTED_MODES:
        raise ValueError(f"unsupported inventory mode: {mode}")

    _verify_repository(source_root)

    if mode == BASE_HEAD:
        if not _string(base_ref):
            raise ValueError("base_ref is required for base_head inventory")
        base_sha = _resolve_commit(source_root, base_ref)
        head_sha = _resolve_commit(source_root, head_ref)
        changed_files = _paths_from_null_output(
            _run_git(
                source_root,
                [
                    "diff",
                    "--name-only",
                    "-z",
                    "--no-ext-diff",
                    GIT_DIFF_FILE_FILTER,
                    f"{base_sha}...{head_sha}",
                    "--",
                ],
            )
        )
        source = GIT_DERIVED_BASE_HEAD
        collections = {
            "base_head_diff": changed_files,
        }
    else:
        if _string(base_ref):
            raise ValueError("base_ref is not valid for staged_worktree inventory")
        base_sha = ""
        head_sha = _resolve_commit(source_root, "HEAD")
        staged = _paths_from_null_output(
            _run_git(
                source_root,
                [
                    "diff",
                    "--cached",
                    "--name-only",
                    "-z",
                    "--no-ext-diff",
                    GIT_DIFF_FILE_FILTER,
                    "--",
                ],
            )
        )
        worktree = _paths_from_null_output(
            _run_git(
                source_root,
                [
                    "diff",
                    "--name-only",
                    "-z",
                    "--no-ext-diff",
                    GIT_DIFF_FILE_FILTER,
                    "--",
                ],
            )
        )
        untracked = _paths_from_null_output(
            _run_git(source_root, ["ls-files", "-z", "--others", "--exclude-standard", "--"])
        )
        changed_files = sorted(set(staged) | set(worktree) | set(untracked))
        source = GIT_DERIVED_STAGED_WORKTREE
        collections = {
            "staged": staged,
            "worktree": worktree,
            "untracked": untracked,
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "collected",
        "mode": mode,
        "repo_root": source_root.as_posix(),
        "base_ref": _string(base_ref),
        "head_ref": _string(head_ref if mode == BASE_HEAD else "HEAD"),
        "base_sha": base_sha,
        "head_sha": head_sha,
        "changed_files": changed_files,
        "changed_files_source": source,
        "collections": collections,
        "git_inventory_verified": True,
        "boundary": {
            "read_only": True,
            "shell_enabled": False,
            "fixed_git_argv_only": True,
            "network_action": False,
            "automation_allowed": False,
            "merge_authorized": False,
        },
    }


def render_markdown(inventory: Mapping[str, Any]) -> str:
    boundary = _as_dict(inventory.get("boundary"))
    changed_files = [_string(item) for item in _as_list(inventory.get("changed_files"))]

    lines = [
        "# Git inventory report",
        "",
        f"- Schema: `{_string(inventory.get('schema_version'))}`",
        f"- Status: `{_string(inventory.get('status'))}`",
        f"- Mode: `{_string(inventory.get('mode'))}`",
        f"- Changed-files source: `{_string(inventory.get('changed_files_source'))}`",
        f"- Changed files: `{len(changed_files)}`",
        f"- Head SHA: `{_string(inventory.get('head_sha'))}`",
        "",
        "## Changed files",
        "",
    ]

    if changed_files:
        lines.extend(f"- `{path}`" for path in changed_files)
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Boundary",
            "",
            f"- Read-only: `{str(_bool(boundary.get('read_only'))).lower()}`",
            f"- Shell enabled: `{str(_bool(boundary.get('shell_enabled'))).lower()}`",
            (f"- Fixed Git argv only: `{str(_bool(boundary.get('fixed_git_argv_only'))).lower()}`"),
            f"- Network action: `{str(_bool(boundary.get('network_action'))).lower()}`",
            f"- Automation allowed: `{str(_bool(boundary.get('automation_allowed'))).lower()}`",
            f"- Merge authorized: `{str(_bool(boundary.get('merge_authorized'))).lower()}`",
            "",
        ]
    )
    return "\n".join(lines)


def write_inventory(inventory: Mapping[str, Any], *, out_dir: Path) -> dict[str, str]:
    json_path = out_dir / INVENTORY_JSON
    markdown_path = out_dir / INVENTORY_MD
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(inventory, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(inventory), encoding="utf-8")
    return {
        "git_inventory_json": json_path.as_posix(),
        "git_inventory_markdown": markdown_path.as_posix(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.git_inventory_collector")
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--mode", choices=list(SUPPORTED_MODES), required=True)
    parser.add_argument("--base-ref", default="")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        inventory = collect_git_inventory(
            repo_root=args.repo_root,
            mode=args.mode,
            base_ref=args.base_ref,
            head_ref=args.head_ref,
        )
        artifacts = write_inventory(inventory, out_dir=args.out_dir)
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        print(f"error={exc}")
        return 2

    if args.format == "json":
        print(
            json.dumps(
                {
                    "status": inventory["status"],
                    "mode": inventory["mode"],
                    "changed_files": inventory["changed_files"],
                    "artifacts": artifacts,
                    "boundary": inventory["boundary"],
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        for key, value in artifacts.items():
            print(f"{key}: {value}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
