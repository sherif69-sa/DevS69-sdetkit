from __future__ import annotations

from pathlib import Path


def test_enterprise_next_pass_template_contains_required_contract_steps():
    path = Path("templates/automations/enterprise-next-pass-handoff.yaml")
    text = path.read_text(encoding="utf-8")

    assert "python -m sdetkit doctor --enterprise-next-pass-only --json --out next-pass.json" in text
    assert "os.environ['GITHUB_OUTPUT']" in text
    assert "def write_output" in text
    assert "<<" in text
    assert "while marker in text" in text
    assert "has_next_pass" in text
    assert "next_pass_command" in text
    assert "next_pass_reason" in text
    assert "needs.enterprise-doctor.outputs.has_next_pass == 'true'" in text
