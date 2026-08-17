## Maintenance Report
- overall: FAIL
- score: 78
- mode: full

| Check | Status | Summary |
| --- | --- | --- |
| clean_tree_check | FAIL | uncommitted changes detected |
| custom_example_check | PASS | example extension check loaded |
| deps_check | PASS | pip dependency graph is consistent |
| doctor_check | PASS | doctor score 67% (2 failed, 8 hint(s)) |
| github_actions_annotation_hygiene | PASS | GitHub Actions annotation hygiene log not configured |
| github_automation_check | PASS | GitHub automation coverage is complete across GHAS, dependency review, and maintenance bots |
| lint_check | PASS | ruff lint and format checks passed |
| security_check | FAIL | security check reported error/warn findings (reproduced); repeated fingerprints: 0b089fcb73af8c9291bdcd5b |
| tests_check | PASS | pytest passed |

### Recommendations
- Review failing checks: clean_tree_check, security_check.
- Suggested next actions: Commit or stash changes, Run security triage summary.
- Doctor hint spotlight: ascii: non-ASCII bytes detected under src/ or tools/ - Replace non-ASCII bytes or relocate binary artifacts outside src/ and tools/.

### Quality signals
- `doctor_check`: 5 passed / 2 failed / 6 skipped; pass rate 71%

### Hint samples
- `doctor_check`
  - ascii: non-ASCII bytes detected under src/ or tools/ - Replace non-ASCII bytes or relocate binary artifacts outside src/ and tools/.
  - clean_tree: working tree has uncommitted changes - Commit or stash local changes.
  - hypothesis: stage-upgrade -&gt; 6.165.10 [backlog-watchlist] - validate with bash quality.sh ci
