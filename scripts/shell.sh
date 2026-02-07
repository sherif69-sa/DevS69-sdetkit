#!/usr/bin/env bash
set -euo pipefail

# Add local venv scripts to PATH for this shell session

if [ -d ".venv/bin" ]; then
PATH="$(pwd)/.venv/bin:$PATH"
export PATH
fi

exec "${SHELL:-bash}" -i
