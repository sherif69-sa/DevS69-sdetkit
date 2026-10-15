"""Every pre-commit hook has one updater, and the autoupdate PR can start CI.

Hooks whose tool is pinned in constraints-ci.txt follow that pin (Dependabot updates it);
the autoupdate workflow updates the rest.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/pre-commit-autoupdate.yml"

# Hook repository -> the constraints-ci.txt package its rev follows.
PINNED_HOOKS = {
    "https://github.com/astral-sh/ruff-pre-commit": "ruff",
    "https://github.com/pre-commit/mirrors-mypy": "mypy",
}


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _hook_repos() -> dict[str, str]:
    config = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    return {repo["repo"]: str(repo["rev"]) for repo in config["repos"] if repo["repo"] != "local"}


def _constraint_pins() -> dict[str, str]:
    text = (ROOT / "constraints-ci.txt").read_text(encoding="utf-8")
    return dict(re.findall(r"(?m)^([A-Za-z0-9_.-]+)==([^\s;#]+)", text))


def test_each_hook_has_exactly_one_updater() -> None:
    autoupdated = set(re.findall(r"--repo (\S+)", _workflow_text()))

    for repo in _hook_repos():
        pinned = repo in PINNED_HOOKS
        assert pinned != (repo in autoupdated), (
            f"{repo} must be updated either by pre-commit autoupdate --repo or by its "
            "constraints-ci.txt pin, not both and not neither"
        )


def test_pinned_hooks_match_their_constraints() -> None:
    pins = _constraint_pins()

    for repo, rev in _hook_repos().items():
        if repo in PINNED_HOOKS:
            package = PINNED_HOOKS[repo]
            assert rev.removeprefix("v") == pins[package], f"{repo} rev {rev} != {package}"


def test_autoupdate_pull_request_is_opened_with_a_token_that_starts_ci() -> None:
    text = _workflow_text()

    assert "token: ${{ secrets.PRE_COMMIT_AUTOUPDATE_TOKEN || github.token }}" in text
    assert "HAS_PR_TOKEN: ${{ secrets.PRE_COMMIT_AUTOUPDATE_TOKEN != '' }}" in text
    assert "if: env.HAS_PR_TOKEN != 'true'" in text
