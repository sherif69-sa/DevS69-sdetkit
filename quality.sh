#!/usr/bin/env bash

set -euo pipefail

mode=${1:-}

case "$mode" in
  test)
    python3 -m pytest -q -W error::RuntimeWarning
    ;;
  cov)
    python3 -m pytest -q -W error::RuntimeWarning --cov=src/sdetkit --cov-report=term-missing --cov-branch --cov-fail-under=95
    ;;
  fmt)
    ruff format .
    ;;
  lint)
    ruff check .
    ;;
  type)
    mypy src/sdetkit
    ;;
  mut)
    mutmut run --paths-to-mutate src/sdetkit --runner "python3 -m pytest -q"
    ;;
  muthtml)
    mutmut html
    echo "open html: mutmut-results.html"
    ;;
  *)
    echo "Usage: bash quality.sh {test|cov|fmt|lint|type|mut|muthtml}" >&2
    exit 2
    ;;
esac
