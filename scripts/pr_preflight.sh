#!/usr/bin/env bash
set -euo pipefail

python -m pre_commit run -a

python -m pytest \
  tests/test_maintenance_on_demand_policy_decisions_workflow.py \
  tests/test_maintenance_on_demand_policy_memory_context_workflow.py \
  tests/test_maintenance_on_demand_policy_history_workflow.py \
  tests/test_maintenance_on_demand_policy_history_store_workflow.py \
  tests/test_maintenance_on_demand_recommendations_workflow.py

python - <<'PY'
from pathlib import Path
import yaml

path = Path(".github/workflows/maintenance-on-demand.yml")
data = yaml.safe_load(path.read_text(encoding="utf-8"))

steps = data["jobs"]["maintenance"]["steps"]
names = [step.get("name", "") for step in steps]

if "Build adaptive maintenance recommendations" in names:
    assert names.index("Build maintenance policy memory context") < names.index(
        "Build adaptive maintenance recommendations"
    )
    assert names.index("Build adaptive maintenance recommendations") < names.index(
        "Record maintenance policy decision history"
    )

print("WORKFLOW ORDER OK")
PY

git diff --check
git status --short
