#!/usr/bin/env bash
# Refresh uv.lock from pyproject.toml, holding every package pinned in
# constraints-ci.txt at its pinned version (`uv lock` alone keeps whatever the
# lock already has). Used by `make lock` and the Dependabot lock-refresh job.
set -euo pipefail
cd "$(dirname "$0")/.."

pins=()
while read -r pin; do
  pins+=(-P "$pin")
done < <(sed -nE 's/^([A-Za-z0-9_.-]+)==([^ ;#]+).*/\1==\2/p' constraints-ci.txt | grep -v '^uv==')

uv lock "${pins[@]}"
