from __future__ import annotations

import json
from pathlib import Path

report = json.loads(Path("pip-audit-report.json").read_text(encoding="utf-8"))
baseline = json.loads(Path(".github/pip-audit-baseline.json").read_text(encoding="utf-8"))
allowed = {(item["id"], item.get("package", "")) for item in baseline}

current: set[tuple[str, str]] = set()
for dep in report.get("dependencies", []):
    pkg = dep.get("name", "")
    for vuln in dep.get("vulns", []):
        current.add((vuln.get("id", ""), pkg))

new = sorted(current - allowed)
if new:
    print("New vulnerabilities found:")
    for vuln_id, pkg in new:
        print(f"- {vuln_id} ({pkg})")
    raise SystemExit(1)

print("No vulnerabilities beyond baseline.")
