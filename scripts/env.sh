#!/usr/bin/env bash

set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

if [ -d ".venv/bin" ]; then
  PATH="$root/.venv/bin:$PATH"
  export PATH
fi
