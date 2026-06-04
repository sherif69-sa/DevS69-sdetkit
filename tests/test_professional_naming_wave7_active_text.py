from __future__ import annotations

from pathlib import Path


def _legacy_next_pass() -> str:
    return "-".join(("next", "pass"))


def _legacy_finish_signal() -> str:
    return "-".join(("finish", "signal"))


def _legacy_closeout() -> str:
    return "".join(("close", "out"))


SCRIPT_ALIASES = {
    "phase1_gate_phase2.py": "baseline_release_readiness_gate.py",
    "phase1_control_loop_report.py": "baseline_control_loop_report.py",
    "phase1_completion_and_prune_plan.py": "baseline_completion_and_prune_plan.py",
    "phase1_blocker_register.py": "baseline_blocker_register.py",
    "phase1_next_pass_card.py": "baseline_followup_pass_card.py",
    "phase1_retire_plan_into_flow.py": "baseline_transition_plan_into_flow.py",
    "phase2_seed_prerequisites.py": "release_readiness_seed_prerequisites.py",
}


def _script(*parts: str) -> Path:
    requested = "_".join(parts)
    return Path("scripts") / SCRIPT_ALIASES.get(requested, requested)


def test_wave7_scripts_use_professional_followup_and_readiness_wording() -> None:
    next_pass_text = _script("phase1", "next", "pass", "card.py").read_text(encoding="utf-8")
    blocker_text = _script("phase1", "blocker", "register.py").read_text(encoding="utf-8")
    gate_text = _script("phase1", "gate", "phase2.py").read_text(encoding="utf-8")

    assert "follow-up pass" in next_pass_text
    assert "baseline follow-up pass remediation card" in next_pass_text
    assert "missing readiness signal or control-loop artifact" in next_pass_text
    assert "missing follow-up pass and control-loop artifacts" in blocker_text
    assert "missing readiness signal or artifact-set payload" in gate_text

    assert "next-pass card for Phase 1 remediation" not in next_pass_text
    assert "missing next-pass and control-loop artifacts" not in blocker_text
    assert f"missing {_legacy_finish_signal()} or artifact-set payload" not in gate_text


def test_wave7_scripts_use_completion_report_wording() -> None:
    files = [
        _script("phase1", "retire", "plan", "into", "flow.py"),
        _script("phase1", "completion", "and", "prune", "plan.py"),
        _script("phase1", "control", "loop", "report.py"),
        _script("phase1", "blocker", "register.py"),
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)

    assert "completion report" in combined
    assert f"before {_legacy_closeout()}" not in combined
    assert f"{_legacy_closeout()} failed" not in combined


def test_wave7_contract_descriptions_use_professional_lane_names() -> None:
    expectations = {
        _script("phase2", "seed", "prerequisites.py"): "release readiness workflows",
        _script(
            "check", "release", "readiness", "hardening", "contract.py"
        ): "release readiness hardening completion-report contract",
        _script(
            "check", "release", "readiness", "wrap", "handoff", "contract.py"
        ): "release readiness wrap + handoff completion-report contract",
        _script(
            "check", "platform", "readiness", "kickoff", "contract.py"
        ): "platform readiness kickoff completion-report contract",
        _script(
            "check", "platform", "readiness", "preplan", "contract.py"
        ): "platform readiness pre-plan completion-report contract",
        _script(
            "check", "platform", "readiness", "wrap", "publication", "contract.py"
        ): "platform readiness wrap publication completion-report contract",
        _script(
            "check", "release", "readiness", "start", "summary", "contract.py"
        ): "release-readiness start summary contract",
        _script(
            "check", "release", "readiness", "kickoff", "contract.py"
        ): "release-readiness kickoff contract",
        _script("check", "baseline", "wrap", "contract.py"): "baseline wrap contract",
    }

    for path, expected in expectations.items():
        assert expected in path.read_text(encoding="utf-8")

    kickoff_text = _script("check", "release", "readiness", "kickoff", "contract.py").read_text(
        encoding="utf-8"
    )
    assert "Validate phase2-kickoff contract." not in kickoff_text
