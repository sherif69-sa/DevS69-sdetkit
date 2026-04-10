#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat <<'USAGE'
usage: scripts/dev.sh <cmd> [--fast]

Commands:
  bootstrap   Create/refresh the pinned toolchain (.venv, deps)
  quality     Run quality gate (quality.sh all)
  security    Run security gate (security.sh)
  test        Run pytest (full suite unless --fast)
  git-health  Print git branch/upstream and ahead/behind status
  all         Run quality + security + tests

Flags:
  --fast      For "test": run a smaller smoke set (no full suite)
  -h,--help   Show help
USAGE
}

cmd="${1:-}"
case "${cmd}" in
  -h|--help|"")
    usage
    exit 0
    ;;
esac
shift || true

fast=0
for a in "$@"; do
  case "$a" in
    --fast) fast=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown arg: $a" >&2; usage; exit 2 ;;
  esac
done

bootstrap() {
  bash "$root/scripts/bootstrap.sh"
}

activate() {
  if [[ ! -f "$root/.venv/bin/activate" ]]; then
    bootstrap
  fi
  # shellcheck disable=SC1091
  . "$root/.venv/bin/activate"
}

run_quality() {
  activate
  bash "$root/quality.sh" all
}

run_security() {
  activate
  bash "$root/security.sh"
}

run_test() {
  activate
  if [[ "$fast" -eq 1 ]]; then
    python -m pytest -q tests/test_security_info_default.py tests/test_ci_templates_bootstrap.py tests/test_gate_scripts_auto_bootstrap.py
  else
    python -m pytest -q
  fi
}

run_git_health() {
  if ! git -C "$root" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "Not a git repository: $root" >&2
    exit 1
  fi

  local branch
  branch="$(git -C "$root" rev-parse --abbrev-ref HEAD)"
  echo "Current branch: $branch"

  if [[ "$branch" == "HEAD" ]]; then
    echo "Upstream branch: NO_UPSTREAM (detached HEAD)"
    echo "Ahead/behind: N/A"
    return 0
  fi

  local upstream
  if ! upstream="$(git -C "$root" rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null)"; then
    echo "Upstream branch: NO_UPSTREAM (set with: git branch --set-upstream-to origin/$branch)"
    echo "Ahead/behind: N/A"
    return 0
  fi

  echo "Upstream branch: $upstream"

  local counts behind ahead
  counts="$(git -C "$root" rev-list --left-right --count "$upstream...HEAD")"
  behind="${counts%%[[:space:]]*}"
  ahead="${counts##*[[:space:]]}"
  echo "Ahead/behind: ahead $ahead, behind $behind"
}

case "$cmd" in
  bootstrap) bootstrap ;;
  quality) run_quality ;;
  security) run_security ;;
  test) run_test ;;
  git-health) run_git_health ;;
  all)
    run_quality
    run_security
    run_test
    ;;
  *)
    echo "unknown cmd: $cmd" >&2
    usage
    exit 2
    ;;
esac
