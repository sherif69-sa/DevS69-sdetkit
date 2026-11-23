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


def _path_or_symlink_exists(p_str: str) -> bool:
    p = Path(p_str)
    if p.exists():
        return True
    parts = p.parts
    if len(parts) >= 2 and parts[0] == "templates" and parts[1] == "ci":
        ci_link = Path("templates/ci")
        if ci_link.is_file():
            target_rel = ci_link.read_text(encoding="utf-8").strip()
            resolved = (ci_link.parent / target_rel / Path(*parts[2:])).resolve()
            return resolved.exists()
    return False


bad.extend([f"missing: {p}" for p in required_templates if not _path_or_symlink_exists(p)])

if bad:
    sys.stderr.write("Repo layout invariant violations:\n" + "\n".join(bad) + "\n")
    raise SystemExit(1)

print("ok: repo layout invariants hold")
