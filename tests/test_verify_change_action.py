"""The verify-change action (`uses: sherif69-sa/DevS69-sdetkit/verify-change@v2`).

The steps' own shell scripts run here against small repositories, with the outputs, job
summary and `gh` that GitHub would provide replaced by files and a fake. Installing sdetkit,
uploading the artifact and signing are not run here: the tests use the interpreter they run
in, and the CI job that runs the action on this repository covers the rest.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from sdetkit import change_verifier

ROOT = Path(__file__).resolve().parents[1]
ACTION = yaml.safe_load((ROOT / "verify-change" / "action.yml").read_text(encoding="utf-8"))
STEPS = {step["name"]: step for step in ACTION["runs"]["steps"]}
EXPRESSION = re.compile(r"\$\{\{\s*(.+?)\s*\}\}")
GITHUB_BASH = ("bash", "--noprofile", "--norc", "-eo", "pipefail", "-c")

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None, reason="needs bash and git"
)

FIXED = "def add(a, b):\n    return a + b\n"
TEST = "from calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _repo(root: Path, head_test: str) -> Path:
    """A base commit with a passing test, then a head commit that changes the test file."""

    (root / "src" / "calc").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "src" / "calc" / "__init__.py").write_text(FIXED, encoding="utf-8")
    (root / "tests" / "test_calc.py").write_text(TEST, encoding="utf-8")
    (root / "pyproject.toml").write_text('[project]\nname = "calc"\nversion = "0"\n')
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")
    (root / "tests" / "test_calc.py").write_text(head_test, encoding="utf-8")
    _git(root, "commit", "-qam", "change", "--allow-empty")
    return root


def _outputs(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    return dict(line.split("=", 1) for line in lines if "=" in line)


class Runner:
    """Runs one action step's script the way the composite action runs it."""

    def __init__(self, tmp_path: Path) -> None:
        self.temp = tmp_path / "runner-temp"
        self.temp.mkdir()
        self.summary = tmp_path / "step-summary.md"
        self.bin = tmp_path / "bin"
        self.bin.mkdir()
        self.values = {
            "inputs.base": "",
            "inputs.head": "",
            "inputs.patch": "",
            "inputs.pytest-args": "",
            "inputs.base-run": "targeted",
            "inputs.runner": "auto",
            "inputs.network": "allow",
            "inputs.python": sys.executable,
            "inputs.fail-on": ACTION["inputs"]["fail-on"]["default"],
            "inputs.working-directory": ".",
            "inputs.github-token": "token",
            "steps.install.outputs.project-python": sys.executable,
            "steps.install.outputs.sdetkit-python": sys.executable,
            "github.event.pull_request.base.sha": "",
            "github.event.pull_request.head.sha": "",
            "github.event.pull_request.number": "7",
            "github.server_url": "https://github.com",
            "github.repository": "owner/repo",
            "github.run_id": "99",
        }

    def run(self, name: str, cwd: Path, **values: str) -> subprocess.CompletedProcess[str]:
        step = STEPS[name]
        self.output = self.temp / f"{step.get('id', 'step')}-output.txt"
        self.output.unlink(missing_ok=True)
        merged = {**self.values, **values}
        env = {
            **os.environ,
            "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}",
            "RUNNER_TEMP": str(self.temp),
            "GITHUB_OUTPUT": str(self.output),
            "GITHUB_STEP_SUMMARY": str(self.summary),
            "GITHUB_REPOSITORY": "owner/repo",
        }
        for key, value in (step.get("env") or {}).items():
            env[key] = EXPRESSION.sub(lambda match: merged[match.group(1)], str(value))
        return subprocess.run(
            # GitHub runs a composite step's `shell: bash` as `bash --noprofile --norc -eo pipefail`.
            [*GITHUB_BASH, step["run"]],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
        )

    def verify(self, repo: Path, **values: str) -> dict[str, str]:
        proc = self.run("Run sdetkit verify change", repo, **values)
        assert proc.returncode == 0, proc.stderr
        outputs = _outputs(self.output)
        self.values["steps.verify.outputs.status"] = outputs["status"]
        self.values["steps.verify.outputs.summary"] = outputs["summary"]
        return outputs


@pytest.fixture
def runner(tmp_path: Path) -> Runner:
    return Runner(tmp_path)


def test_a_new_test_on_top_is_verified_with_head_tilde_one_as_the_base(
    tmp_path: Path, runner: Runner
) -> None:
    more = TEST + "\n\ndef test_zero():\n    assert add(0, 0) == 0\n"
    repo = _repo(tmp_path / "repo", more)

    outputs = runner.verify(repo)

    assert outputs["status"] == "VERIFIED", runner.summary.read_text(encoding="utf-8")
    assert outputs["verdict"] == "SHIP"
    assert json.loads(Path(outputs["attestation"]).read_text(encoding="utf-8"))["subject"]
    assert Path(outputs["predicate"]).is_file()
    summary = runner.summary.read_text(encoding="utf-8")
    assert summary.startswith("### :white_check_mark: SDETKit verify change: VERIFIED")
    assert "| Change | 2 passed, 0 failed, 0 skipped |" in summary
    assert runner.run("Apply fail-on", repo).returncode == 0


def test_an_emptied_test_reads_review_and_strict_fail_on_blocks_it(
    tmp_path: Path, runner: Runner
) -> None:
    repo = _repo(tmp_path / "repo", TEST.replace("assert add(2, 3) == 5", "add(2, 3)"))

    outputs = runner.verify(repo)

    assert outputs["status"] == "REVIEW"
    summary = runner.summary.read_text(encoding="utf-8")
    assert summary.startswith("### :warning: SDETKit verify change: REVIEW")
    assert "**assertions_removed**" in summary
    assert "`tests/test_calc.py::test_add (1 -> 0)`" in summary
    # The default lets a person decide; a stricter policy blocks the merge.
    assert runner.run("Apply fail-on", repo).returncode == 0
    strict = runner.run("Apply fail-on", repo, **{"inputs.fail-on": "FAILED,NOT_RUN,REVIEW"})
    assert strict.returncode == 1
    assert "::error title=SDETKit verify change::Status REVIEW" in strict.stdout


def test_the_pull_request_change_starts_where_it_branched(tmp_path: Path, runner: Runner) -> None:
    # main moved on after the branch was cut: its new file is not part of the change.
    repo = _repo(tmp_path / "repo", TEST)
    branch_point = _git(repo, "rev-parse", "HEAD").strip()
    _git(repo, "checkout", "-qb", "feature")
    (repo / "tests" / "test_more.py").write_text(
        "from calc import add\n\n\ndef test_more():\n    assert add(1, 1) == 2\n"
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "feature")
    head = _git(repo, "rev-parse", "HEAD").strip()
    _git(repo, "checkout", "-q", "-")
    (repo / "NOTES.md").write_text("main moved on\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "main moves on")
    main_tip = _git(repo, "rev-parse", "HEAD").strip()

    outputs = runner.verify(
        repo,
        **{
            "github.event.pull_request.base.sha": main_tip,
            "github.event.pull_request.head.sha": head,
        },
    )

    report = json.loads(Path(outputs["report"]).read_text(encoding="utf-8"))
    assert report["change"]["base_sha"] == branch_point
    assert [entry["path"] for entry in report["change"]["changed"]] == ["tests/test_more.py"]
    assert outputs["status"] == "VERIFIED"


def test_a_bad_ref_reads_not_run_and_fails_the_step(tmp_path: Path, runner: Runner) -> None:
    repo = _repo(tmp_path / "repo", TEST)

    outputs = runner.verify(repo, **{"inputs.base": "no-such-ref"})

    assert outputs["status"] == "NOT_RUN"
    assert outputs["predicate"] == ""
    summary = runner.summary.read_text(encoding="utf-8")
    assert summary.startswith("### :white_circle: SDETKit verify change: NOT_RUN")
    assert "not a commit" in summary
    assert runner.run("Apply fail-on", repo).returncode == 1


def _fake_gh(runner: Runner) -> Path:
    log = runner.temp / "gh.log"
    script = runner.bin / "gh"
    script.write_text(
        "#!/usr/bin/env bash\n"
        f'echo "$*" >> "{log}"\n'
        'case "$*" in *--jq*) printf "%s" "$FAKE_EXISTING"; exit 0;; esac\n'
        'while [ $# -gt 0 ]; do [ "$1" = --input ] && cat "$2" >> '
        f'"{log}"; shift; done\n'
    )
    script.chmod(0o755)
    return log


@pytest.mark.parametrize(
    ("existing", "call"),
    [("", "api --method POST repos/owner/repo/issues/7/comments"), ("42", "PATCH")],
)
def test_one_pull_request_comment_is_posted_then_updated(
    tmp_path: Path, runner: Runner, existing: str, call: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_EXISTING", existing)
    repo = _repo(tmp_path / "repo", TEST + "\n\ndef test_two():\n    assert add(1, 1) == 2\n")
    runner.verify(repo)
    log = _fake_gh(runner)

    proc = runner.run("Comment on the pull request", repo)

    assert proc.returncode == 0, proc.stderr
    text = log.read_text(encoding="utf-8")
    assert call in text
    if existing:
        assert "repos/owner/repo/issues/comments/42" in text
    body = json.loads(text.splitlines()[-1])["body"]
    assert body.startswith(
        "<!-- sdetkit-verify-change:. -->\n### :white_check_mark: SDETKit verify change"
    )
    assert body.rstrip().endswith(
        "[Workflow run and evidence](https://github.com/owner/repo/actions/runs/99)"
    )


def test_a_comment_that_cannot_be_posted_only_warns(tmp_path: Path, runner: Runner) -> None:
    repo = _repo(tmp_path / "repo", TEST)
    runner.verify(repo)
    (runner.bin / "gh").write_text("#!/usr/bin/env bash\nexit 1\n")
    (runner.bin / "gh").chmod(0o755)

    proc = runner.run("Comment on the pull request", repo)

    assert proc.returncode == 0
    assert "::warning title=SDETKit verify change::Could not comment" in proc.stdout


def test_scripts_read_inputs_only_through_the_environment() -> None:
    """`${{ }}` inside a script would let a branch name or argument inject shell code."""

    declared = set(ACTION["inputs"])
    for step in ACTION["runs"]["steps"]:
        if "run" not in step:
            continue
        assert "${{" not in step["run"], step["name"]
        for value in (step.get("env") or {}).values():
            for expression in EXPRESSION.findall(str(value)):
                if expression.startswith("inputs."):
                    assert expression.removeprefix("inputs.") in declared
    assert set(ACTION["outputs"]) == {
        "status",
        "verdict",
        "report",
        "summary",
        "attestation",
        "patch",
    }
    install = STEPS["Install sdetkit"]["run"]
    assert '"$GITHUB_ACTION_PATH/.."' in install  # the tagged action installs its own source
    # Every action it uses is pinned to a commit.
    for step in ACTION["runs"]["steps"]:
        if "uses" in step:
            assert re.fullmatch(r"[\w-]+/[\w-]+@[0-9a-f]{40}", step["uses"]), step["uses"]


def test_the_summary_lists_findings_and_test_changes() -> None:
    report = {
        "status": "REVIEW",
        "change": {"base_sha": "a" * 40, "head_sha": "b" * 40, "changed": [{}, {}]},
        "tests": {
            "base": {"counts": {"passed": 3, "failed": 0, "skipped": 0}},
            "head": {"counts": {"passed": 2, "failed": 0, "skipped": 0}},
            "comparison": {
                "regressions": [],
                "new_failures": [],
                "missing": ["tests.test_x::test_gone"],
                "now_skipped": [],
                "still_failing": [],
                "fixed": [],
            },
        },
        "reasons": ["tests_removed: Tests that existed before the change are gone."],
        "findings": [
            {
                "code": "test_harness_changed",
                "message": "conftest changed.",
                "blocking": False,
                "items": ["conftest.py"],
            },
            {
                "code": "tests_removed",
                "message": "Tests are gone.",
                "blocking": True,
                "items": [f"tests/test_x.py::test_{n}" for n in range(7)],
            },
        ],
        "next_action": "Read the findings.",
    }

    text = change_verifier.render_summary(report)

    assert text.splitlines()[0] == "### :warning: SDETKit verify change: REVIEW"
    assert "`aaaaaaaaaaaa` → `bbbbbbbbbbbb`, 2 file(s) changed." in text
    assert "| Base | 3 passed, 0 failed, 0 skipped |" in text
    # Blocking findings first, then notes; long lists are cut.
    assert text.index("**tests_removed**") < text.index("**test_harness_changed** (note)")
    assert "and 2 more" in text
    assert "<details><summary>Ran before, did not run now (1)</summary>" in text
    assert "**Next:** Read the findings." in text


def test_steps_that_read_exit_codes_turn_errexit_off() -> None:
    """GitHub runs `bash -e`: without `set +e`, a nonzero exit ends the step before it is read."""

    for step in ACTION["runs"]["steps"]:
        script = step.get("run", "")
        if "$?" in script:
            assert "set +e" in script, step["name"]
