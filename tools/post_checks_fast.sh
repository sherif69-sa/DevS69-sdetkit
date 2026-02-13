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

OUT_DIR="${POST_CHECKS_OUT_DIR:-$ROOT/.sdetkit/post-checks-fast}"
mkdir -p "$OUT_DIR"

echo "[post-checks-fast] compileall"
python3 -m compileall -q src tools

echo "[post-checks-fast] pytest"
pytest -q

echo "[post-checks-fast] doctor --ci"
sdetkit doctor --ci

echo "[post-checks-fast] deterministic exporter smoke (json + md)"
sdetkit repo audit . --profile enterprise --fail-on none --format json > "$OUT_DIR/audit-1.json"
sdetkit repo audit . --profile enterprise --fail-on none --format json > "$OUT_DIR/audit-2.json"
diff -u "$OUT_DIR/audit-1.json" "$OUT_DIR/audit-2.json"

sdetkit repo audit . --profile enterprise --fail-on none --format md > "$OUT_DIR/audit-1.md"
sdetkit repo audit . --profile enterprise --fail-on none --format md > "$OUT_DIR/audit-2.md"
diff -u "$OUT_DIR/audit-1.md" "$OUT_DIR/audit-2.md"

echo "[post-checks-fast] done"
