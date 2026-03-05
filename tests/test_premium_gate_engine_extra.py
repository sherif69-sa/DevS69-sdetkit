from __future__ import annotations

from sdetkit import premium_gate_engine as eng


def test_knowledge_recommendations_and_autofix_helpers() -> None:
    warnings = [eng._make_signal("security", "sql", "high", "x")]
    checks = [eng._make_signal("doctor", "policy", "warn", "y")]
    steps = [eng.StepStatus("CI", ok=False, log_path="p", details="d", warnings_count=0)]

    recs = eng._knowledge_recommendations(warnings, checks, steps)
    assert any(r.category == "step-failures" for r in recs)
    assert any(r.category == "artifact-integrity" for r in recs)

    t1, c1 = eng._autofix_timeout("requests.get(url)\n")
    assert c1 is True and "timeout=10" in t1
    t2, c2 = eng._autofix_shell_true("subprocess.run('x', shell=True)")
    assert c2 is True and "shell=False" in t2
    t3, c3 = eng._autofix_yaml_load("yaml.load(data)")
    assert c3 is True and "safe_load" in t3


def test_build_fix_plan_item_fields() -> None:
    item = eng._build_fix_plan_item(
        eng.AutoFixResult("SEC_X", "src/a.py", "manual", "needs review")
    )
    assert item.rule_id == "SEC_X"
    assert item.priority == "medium"
