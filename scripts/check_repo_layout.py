import sys
from pathlib import Path

bad = []

bad.extend([str(p) for p in Path("docs/roadmap/plans").glob(".*.json")])

legacy_root = [
    ".gitlab-ci.cycle66-advanced-reference.yml",
    ".jenkins.cycle67-advanced-reference.Jenkinsfile",
    ".tekton.cycle68-self-hosted-reference.yaml",
]
bad.extend([f"forbidden: {p}" for p in legacy_root if Path(p).exists()])

required_templates = [
    "templates/ci/gitlab/gitlab-advanced-reference.yml",
    "templates/ci/jenkins/jenkins-advanced-reference.Jenkinsfile",
    "templates/ci/tekton/tekton-self-hosted-reference.yaml",
]
bad.extend([f"missing: {p}" for p in required_templates if not Path(p).exists()])

if bad:
    sys.stderr.write("Repo layout invariant violations:\n" + "\n".join(bad) + "\n")
    raise SystemExit(1)

print("ok: repo layout invariants hold")
