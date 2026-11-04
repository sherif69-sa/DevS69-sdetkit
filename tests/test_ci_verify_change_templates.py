"""The GitLab CI and Jenkins templates for `verify change` run it for real.

`examples/adoption/gitlab/sdetkit-verify-change.gitlab-ci.yml` and
`examples/adoption/jenkins/sdetkit-verify-change.Jenkinsfile` work out the merge or pull
request's change the way their CI names it and verify it. The end-to-end tests execute each
template's shell steps on a fixture repository with a fix, a weakened test and a break, with
SDETKit installed from this checkout (the `SDETKIT_PACKAGE` variable); they need the network
and run in CI's "CI templates (self)" job.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
GITLAB = ROOT / "examples/adoption/gitlab/sdetkit-verify-change.gitlab-ci.yml"
JENKINS = ROOT / "examples/adoption/jenkins/sdetkit-verify-change.Jenkinsfile"
VERSION = re.search(
    r'^version = "([^"]+)"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.M
)
GITLAB_JOB_KEYS = {
    "stage",
    "image",
    "variables",
    "rules",
    "allow_failure",
    "before_script",
    "script",
    "after_script",
    "artifacts",
}
REPORT = "build/sdetkit/change-verification/change-verification.json"


def _gitlab_job() -> dict[str, Any]:
    data = yaml.safe_load(GITLAB.read_text(encoding="utf-8"))
    assert list(data) == ["sdetkit-verify-change"]
    job: dict[str, Any] = data["sdetkit-verify-change"]
    return job


def _jenkins() -> tuple[dict[str, str], str, str]:
    """The environment block, the setup stage's script and the verify stage's script."""

    text = JENKINS.read_text(encoding="utf-8")
    environment = dict(re.findall(r"^\s*([A-Z_]+) = '([^']*)'$", text, re.M))
    setup = re.search(r"sh '''(.*?)'''", text, re.S)
    verify = re.search(r"sh\(returnStatus: true, script: '''(.*?)'''\)", text, re.S)
    assert setup and verify
    return environment, setup[1], verify[1]


def test_the_gitlab_job_verifies_the_merge_request_and_keeps_its_evidence() -> None:
    job = _gitlab_job()

    assert set(job) <= GITLAB_JOB_KEYS
    assert [rule["if"] for rule in job["rules"]] == ['$CI_PIPELINE_SOURCE == "merge_request_event"']
    # REVIEW warns; FAILED and NOT_RUN (exit code 2) fail.
    assert job["allow_failure"] == {"exit_codes": [1]}
    assert job["variables"]["GIT_DEPTH"] == "0"
    assert job["artifacts"]["when"] == "always"
    assert (
        job["artifacts"]["reports"]["junit"] == "build/sdetkit/change-verification/tests-head.xml"
    )
    assert re.fullmatch(r"[A-Za-z0-9 _-]+", job["artifacts"]["expose_as"])
    script = "\n".join(job["script"])
    assert '--base "$CI_MERGE_REQUEST_DIFF_BASE_SHA" --head "$CI_COMMIT_SHA"' in script


def test_both_templates_pin_this_release_and_jenkins_maps_the_statuses() -> None:
    assert VERSION is not None
    pin = f"sdetkit=={VERSION[1]}"
    text = JENKINS.read_text(encoding="utf-8")

    assert _gitlab_job()["variables"]["SDETKIT_PACKAGE"] == pin
    assert _jenkins()[0]["SDETKIT_PACKAGE"] == pin
    assert "when { changeRequest() }" in text
    assert "if (status == 1) {\n            unstable(" in text
    assert "} else if (status != 0) {\n            error(" in text
    assert "junit allowEmptyResults: true" in text


@pytest.mark.skipif(sys.platform == "win32", reason="the templates' steps are POSIX shell")
def test_every_shell_step_parses() -> None:
    job = _gitlab_job()
    _, setup, verify = _jenkins()

    for step in ("\n".join(job["before_script"] + job["script"]), setup, verify):
        proc = subprocess.run(["sh", "-n", "-c", step], capture_output=True, text=True)
        assert proc.returncode == 0, f"{step}\n{proc.stderr}"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


ADD = "def add(a, b):\n    return a + b\n"
TEST = "from app import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n\n\ndef test_zero():\n    assert add(0, 0) == 0\n"
# The change each fixture makes, and what it reads.
CHANGES = {
    "VERIFIED": {"src/app/__init__.py": ADD + "\n\ndef sub(a, b):\n    return a - b\n"},
    "REVIEW": {"tests/test_add.py": TEST.split("\n\n\ndef test_zero")[0] + "\n"},
    "FAILED": {"src/app/__init__.py": "def add(a, b):\n    return a - b\n"},
}
EXIT_CODES = {"VERIFIED": 0, "REVIEW": 1, "FAILED": 2}


def _repository(root: Path, status: str) -> tuple[Path, str, str]:
    """A bare origin with main, and a clone at a change on top of it: (clone, base, head)."""

    seed = root / "seed"
    (seed / "src/app").mkdir(parents=True)
    (seed / "tests").mkdir()
    (seed / "pyproject.toml").write_text(
        '[project]\nname = "app"\nversion = "0.1.0"\n\n'
        '[project.optional-dependencies]\ntest = ["pytest"]\n\n'
        '[tool.setuptools.packages.find]\nwhere = ["src"]\n'
    )
    (seed / "src/app/__init__.py").write_text(ADD)
    (seed / "tests/test_add.py").write_text(TEST)
    (seed / ".gitignore").write_text("build/\n*.egg-info/\n.venv/\n__pycache__/\n")
    _git(seed, "init", "-q", "-b", "main")
    _git(seed, "add", "-A")
    _git(seed, "commit", "-qm", "base")
    origin = root / "origin.git"
    _git(root, "clone", "-q", "--bare", str(seed), str(origin))
    clone = root / "clone"
    _git(root, "clone", "-q", str(origin), str(clone))
    base = _git(clone, "rev-parse", "HEAD")
    _git(clone, "checkout", "-qb", "change")
    for path, text in CHANGES[status].items():
        (clone / path).write_text(text)
    _git(clone, "commit", "-qam", "change")
    return clone, base, _git(clone, "rev-parse", "HEAD")


def _agent(tmp_path: Path) -> dict[str, str]:
    image = tmp_path / "image"
    subprocess.run([sys.executable, "-m", "venv", str(image)], check=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("VIRTUAL_ENV", "PYTHON"))}
    env["PATH"] = f"{image / 'bin'}{os.pathsep}{os.environ['PATH']}"
    env["SDETKIT_PACKAGE"] = str(ROOT)
    env["SDETKIT_ARGS"] = ""
    return env


def _run(script: str, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", "-e", "-c", script], cwd=cwd, env=env, capture_output=True, text=True, timeout=900
    )


def _status(clone: Path) -> str:
    status: str = json.loads((clone / REPORT).read_text(encoding="utf-8"))["status"]
    assert status in (clone / "build/sdetkit/verify-change.md").read_text(encoding="utf-8")
    return status


@pytest.mark.network
@pytest.mark.skipif(sys.platform == "win32", reason="the templates' steps are POSIX shell")
@pytest.mark.parametrize("status", ["VERIFIED", "REVIEW", "FAILED"])
def test_the_gitlab_job_verifies_the_merge_request(tmp_path: Path, status: str) -> None:
    job = _gitlab_job()
    clone, base, head = _repository(tmp_path, status)
    env = {
        **_agent(tmp_path),
        "CI_MERGE_REQUEST_DIFF_BASE_SHA": base,
        "CI_COMMIT_SHA": head,
    }

    proc = _run("\n".join(job["before_script"] + job["script"]), clone, env)

    assert proc.returncode == EXIT_CODES[status], proc.stdout + proc.stderr
    assert _status(clone) == status


@pytest.mark.network
@pytest.mark.skipif(sys.platform == "win32", reason="the templates' steps are POSIX shell")
@pytest.mark.parametrize("status", ["VERIFIED", "REVIEW", "FAILED"])
def test_the_jenkins_stage_verifies_the_pull_request(tmp_path: Path, status: str) -> None:
    environment, setup, verify = _jenkins()
    clone, _, _ = _repository(tmp_path, status)
    env = {**environment, **_agent(tmp_path), "CHANGE_TARGET": "main"}

    assert _run(setup, clone, env).returncode == 0
    proc = _run(verify, clone, env)

    assert proc.returncode == EXIT_CODES[status], proc.stdout + proc.stderr
    assert _status(clone) == status
