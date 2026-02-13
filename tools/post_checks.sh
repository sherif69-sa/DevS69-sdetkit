#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -d ".venv/bin" ]]; then
  PATH="$ROOT/.venv/bin:$PATH"
  export PATH
fi

export PYTHONHASHSEED="${PYTHONHASHSEED:-0}"
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-1700000000}"

OUT_DIR="${POST_CHECKS_OUT_DIR:-$ROOT/.sdetkit/post-checks}"
mkdir -p "$OUT_DIR"

RELEASE_TAG=""
if [[ "${1:-}" == "--release-tag" ]]; then
  RELEASE_TAG="${2:-}"
  if [[ -z "$RELEASE_TAG" ]]; then
    echo "usage: tools/post_checks.sh [--release-tag vX.Y.Z]" >&2
    exit 2
  fi
fi

echo "[post-checks] compileall"
python3 -m compileall -q src tools

echo "[post-checks] pytest"
pytest -q

echo "[post-checks] pre-commit"
python -m pre_commit run -a

echo "[post-checks] doctor --all"
sdetkit doctor --all

echo "[post-checks] deterministic exporter smoke (json + md)"
sdetkit repo audit . --profile enterprise --fail-on none --format json > "$OUT_DIR/audit-1.json"
sdetkit repo audit . --profile enterprise --fail-on none --format json > "$OUT_DIR/audit-2.json"
diff -u "$OUT_DIR/audit-1.json" "$OUT_DIR/audit-2.json"

sdetkit repo audit . --profile enterprise --fail-on none --format md > "$OUT_DIR/audit-1.md"
sdetkit repo audit . --profile enterprise --fail-on none --format md > "$OUT_DIR/audit-2.md"
diff -u "$OUT_DIR/audit-1.md" "$OUT_DIR/audit-2.md"

echo "[post-checks] packaging build (sdist/wheel)"
python -m build
python -m twine check dist/*

if [[ -n "$RELEASE_TAG" ]]; then
  echo "[post-checks] release tag/version verification: $RELEASE_TAG"
  python scripts/check_release_tag_version.py "$RELEASE_TAG"
fi

echo "[post-checks] done"
