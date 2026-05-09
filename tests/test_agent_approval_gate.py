from __future__ import annotations

import sys

from sdetkit.agent.core import ApprovalGate


def test_safe_action_does_not_prompt() -> None:
    calls: list[str] = []
    gate = ApprovalGate(answer_reader=lambda prompt: calls.append(prompt) or "yes\n")

    approved, reason = gate.approve("repo.audit", {"profile": "default"})

    assert approved is True
    assert reason == "not-dangerous"
    assert calls == []


def test_auto_approve_bypasses_prompt_for_dangerous_action() -> None:
    calls: list[str] = []
    gate = ApprovalGate(
        auto_approve=True,
        answer_reader=lambda prompt: calls.append(prompt) or "no\n",
    )

    approved, reason = gate.approve("shell.run", {"cmd": "echo ok"})

    assert approved is True
    assert reason == "auto-approved"
    assert calls == []


def test_non_interactive_dangerous_action_is_denied(monkeypatch) -> None:
    class NonInteractiveStdin:
        def isatty(self) -> bool:
            return False

    monkeypatch.setattr(sys, "stdin", NonInteractiveStdin())

    calls: list[str] = []
    gate = ApprovalGate(answer_reader=lambda prompt: calls.append(prompt) or "yes\n")

    approved, reason = gate.approve("shell.run", {"cmd": "echo ok"})

    assert approved is False
    assert reason == "approval required (non-interactive)"
    assert calls == []


def test_interactive_yes_approves_dangerous_action(monkeypatch) -> None:
    class InteractiveStdin:
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr(sys, "stdin", InteractiveStdin())

    prompts: list[str] = []
    gate = ApprovalGate(answer_reader=lambda prompt: prompts.append(prompt) or "yes\n")

    approved, reason = gate.approve("shell.run", {"cmd": "echo ok"})

    assert approved is True
    assert reason == "approved"
    assert len(prompts) == 1
    assert "approve dangerous action" in prompts[0]


def test_interactive_no_denies_dangerous_action(monkeypatch) -> None:
    class InteractiveStdin:
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr(sys, "stdin", InteractiveStdin())

    gate = ApprovalGate(answer_reader=lambda prompt: "no\n")

    approved, reason = gate.approve("shell.run", {"cmd": "echo ok"})

    assert approved is False
    assert reason == "denied"


def test_fs_write_outside_workdir_requires_approval() -> None:
    gate = ApprovalGate(auto_approve=True)

    assert gate.requires_approval("fs.write", {"path": "README.md"}) is True


def test_fs_write_inside_agent_workdir_does_not_require_approval() -> None:
    gate = ApprovalGate()

    assert (
        gate.requires_approval(
            "fs.write",
            {"path": ".sdetkit/agent/workdir/report.json"},
        )
        is False
    )


def test_fs_write_normalizes_leading_slashes_and_backslashes() -> None:
    gate = ApprovalGate()

    assert (
        gate.requires_approval(
            "fs.write",
            {"path": ".sdetkit\\\\agent\\\\workdir\\\\report.json"},
        )
        is False
    )


def test_unc_style_fs_write_path_still_requires_approval() -> None:
    gate = ApprovalGate()

    assert (
        gate.requires_approval(
            "fs.write",
            {"path": "\\\\server\\share\\.sdetkit\\agent\\workdir\\report.json"},
        )
        is True
    )
