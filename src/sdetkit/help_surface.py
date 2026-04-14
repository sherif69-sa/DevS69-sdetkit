from __future__ import annotations

import argparse

from .legacy_commands import LEGACY_NAMESPACE_COMMANDS


def is_hidden_command(name: str) -> bool:
    if name == "playbooks":
        return False
    if name == "legacy":
        return False
    if name in {
        "docs-qa",
        "docs-nav",
        "github-actions-quickstart",
        "gitlab-ci-quickstart",
        "quality-contribution-delta",
        "proof",
    }:
        return True
    if name in LEGACY_NAMESPACE_COMMANDS:
        return True
    if name.startswith("impact") and len(name) > 3 and name[3].isdigit():
        return True
    if name.endswith("-closeout"):
        return True
    return False


def filter_hidden_subcommands(parser: argparse.ArgumentParser) -> None:
    for action in parser._actions:
        if not hasattr(action, "_choices_actions"):
            continue
        filtered = []
        for choice_action in list(getattr(action, "_choices_actions", [])):
            name = getattr(choice_action, "dest", "")
            help_text = getattr(choice_action, "help", None)
            if help_text == argparse.SUPPRESS:
                continue
            if is_hidden_command(name):
                continue
            filtered.append(choice_action)
        action._choices_actions = filtered


def hide_help_subcommands(sub) -> None:
    actions = getattr(sub, "_choices_actions", None)
    if not isinstance(actions, list):
        return
    filtered = []
    for a in actions:
        name = getattr(a, "name", "")
        if isinstance(name, str) and is_hidden_command(name):
            continue
        filtered.append(a)
    sub._choices_actions = filtered
