#!/usr/bin/env bash

set -euo pipefail

if [ -f .venv/bin/activate ]; then
  # shellcheck disable=SC1091
  . .venv/bin/activate
fi

mode=${1:-}

case "$mode" in
  quick)
    PYTHONPATH=src pytest -q
    ;;
  docker)
    docker build -t sdet-bootcamp:ci .
    docker run --rm sdet-bootcamp:ci
    ;;
  all)
    PYTHONPATH=src pytest -q
    docker build -t sdet-bootcamp:ci .
    docker run --rm sdet-bootcamp:ci
    ;;
  *)
    echo "Usage: bash ci.sh {quick|docker|all}" >&2
    exit 2
    ;;
esac
