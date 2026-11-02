#!/usr/bin/env bash
# Refresh uv.lock from pyproject.toml, holding every package pinned in
# constraints-ci.txt at its pinned version (`uv lock` alone keeps whatever the
# lock already has). Used by `make lock` and the Dependabot lock-refresh job.
#
# A package pinned per Python version (`pkg==A; python_version < "3.11"` and
# `pkg==B; python_version >= "3.11"`) cannot take two `-P pkg==X` pins, so it is
# upgraded by name: uv picks the newest version each Python range allows, and
# tests/test_dependency_lock.py fails if that is not the pinned one.
set -euo pipefail
cd "$(dirname "$0")/.."

pins=()
while read -r pin; do
  pins+=(-P "$pin")
done < <(sed -nE '/;/!s/^([A-Za-z0-9_.-]+)==([^ ;#]+).*/\1==\2/p' constraints-ci.txt | grep -v '^uv==')
while read -r name; do
  pins+=(-P "$name")
done < <(sed -nE 's/^([A-Za-z0-9_.-]+)==[^ ;#]+ *;.*/\1/p' constraints-ci.txt | sort -u)

uv lock "${pins[@]}"
