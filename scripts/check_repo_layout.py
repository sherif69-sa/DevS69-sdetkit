import sys
from pathlib import Path

bad = [str(p) for p in Path("docs/roadmap/plans").glob(".*.json")]

legacy_root = [
    ".gitlab-ci.day66-advanced-reference.yml",
    ".jenkins.day67-advanced-reference.Jenkinsfile",
    ".tekton.day68-self-hosted-reference.yaml",
]
bad.extend([p for p in legacy_root if Path(p).exists()])

if bad:
    sys.stderr.write("Found forbidden legacy repo-layout paths:\n" + "\n".join(bad) + "\n")
    raise SystemExit(1)

print("ok: repo layout invariants hold")
