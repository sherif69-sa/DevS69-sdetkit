#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

MODE="${1:-quick}"

if [[ "$MODE" != "quick" && "$MODE" != "release" ]]; then
  echo "Usage: bash scripts/ready_to_use.sh [quick|release]" >&2
  exit 2
fi

echo "[1/4] Bootstrapping development environment..."
bash scripts/bootstrap.sh

# shellcheck disable=SC1091
source .venv/bin/activate

echo "[2/4] Validating CLI availability..."
python -m sdetkit --help >/dev/null
python -m sdetkit doctor --format text >/dev/null

echo "[3/4] Running CI quick lane..."
if bash ci.sh quick --skip-docs; then
  CI_RC=0
else
  CI_RC=$?
fi

if [[ "$MODE" == "release" ]]; then
  echo "[4/4] Running release-confidence lane (strict)..."
  bash quality.sh cov
  python -m sdetkit security enforce --format json --max-error 0 --max-warn 0 --max-info 0
  python -m sdetkit gate release
fi

if [[ "$CI_RC" -ne 0 ]]; then
  if [[ "$MODE" == "quick" ]]; then
    echo "Quick setup completed, but CI quick lane reported issues (rc=$CI_RC)."
    echo "You can still start working; fix issues incrementally with 'bash quality.sh full-test'."
    exit 0
  fi
  echo "Release mode failed because CI quick lane returned rc=$CI_RC." >&2
  exit "$CI_RC"
fi

if [[ "$MODE" == "quick" ]]; then
  echo "[4/4] Quick mode complete."
  echo "Run 'bash scripts/ready_to_use.sh release' for full release-confidence checks."
fi

echo "Repository is ready to use."
