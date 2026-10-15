"""Every pre-commit hook has one updater, and the autoupdate PR can start CI.

Hooks whose tool is pinned in constraints-ci.txt follow that pin (Dependabot updates it,
and scripts/sync_pre_commit_revs.py copies it into the rev); the autoupdate workflow
updates the rest.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/pre-commit-autoupdate.yml"

_spec = importlib.util.spec_from_file_location(
    "sync_pre_commit_revs", ROOT / "scripts/sync_pre_commit_revs.py"
)
assert _spec and _spec.loader
sync_revs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync_revs)
PINNED_HOOKS = sync_revs.PINNED_HOOKS


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _hook_repos() -> dict[str, str]:
    config = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    return {repo["repo"]: str(repo["rev"]) for repo in config["repos"] if repo["repo"] != "local"}


def _constraint_pins() -> dict[str, str]:
    return sync_revs.constraint_pins((ROOT / "constraints-ci.txt").read_text(encoding="utf-8"))


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


def test_sync_sets_pinned_hook_revs_from_constraints() -> None:
    config = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    pins = {**_constraint_pins(), "ruff": "9.9.9", "mypy": "8.8.8"}

    synced = sync_revs.sync(config, pins)

    revs = {repo["repo"]: repo["rev"] for repo in yaml.safe_load(synced)["repos"] if "rev" in repo}
    assert revs["https://github.com/astral-sh/ruff-pre-commit"] == "v9.9.9"
    assert revs["https://github.com/pre-commit/mirrors-mypy"] == "v8.8.8"
    assert (
        revs["https://github.com/pre-commit/pre-commit-hooks"]
        == _hook_repos()["https://github.com/pre-commit/pre-commit-hooks"]
    )
    assert sync_revs.sync(config, _constraint_pins()) == config
