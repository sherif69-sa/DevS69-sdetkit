# Issue-driven task proposals (2026-04-26)

This pass captures four concrete follow-up tasks from reviewing lane 67 (`integration-expansion3-closeout`) code and tests.

## 1) Typo-fix task (P3)

**Issue**
- The lane header text is malformed markdown (`#  — ...` has an extra space after `#`) and multiple template lines include double-space placeholder artifacts (for example `"The  lane"`, `" closeout"`).

**Evidence**
- `src/sdetkit/integration_expansion3_closeout_67.py`: `_SECTION_HEADER`, `_DEFAULT_PAGE_TEMPLATE`, and required contract/delivery lines.

**Proposed task**
- Normalize heading format to valid markdown style (`# ...`).
- Replace placeholder-driven double-space phrases with explicit lane nouns.

**Acceptance criteria**
- Generated page and emitted pack docs contain no `#  ` prefix and no orphan placeholder phrases like `"The  lane"`.

---

## 2) Bug-fix task (P1)

**Issue**
- Two checks are currently non-informative / always true:
  1. `top10_strategy_alignment` checks `"" in top10_text and "" in top10_text`.
  2. `integration_expansion2_board_integrity` passes a blank needle (`""`) into `_count_board_items`, making `needle in text` always true.

**Evidence**
- `src/sdetkit/integration_expansion3_closeout_67.py`: `_count_board_items`, call-site with `""`, and the `top10_strategy_alignment` check block.

**Proposed task**
- Replace empty-string checks with explicit required markers.
- Require a real board anchor token when evaluating `integration_expansion2_board_integrity`.

**Acceptance criteria**
- If top-10 markers are removed, `top10_strategy_alignment` fails.
- If board anchor text is removed, `integration_expansion2_board_integrity` fails.

---

## 3) Documentation discrepancy task (P2)

**Issue**
- The documented command lane and runtime execution lane diverge:
  - Docs/template + required commands include an `--execute` command.
  - `_EXECUTION_COMMANDS` does not run that command and instead uses contract script with `--skip-evidence`.

**Evidence**
- `src/sdetkit/integration_expansion3_closeout_67.py`: `_REQUIRED_COMMANDS`, `_EXECUTION_COMMANDS`, `_DEFAULT_PAGE_TEMPLATE`.

**Proposed task**
- Create one canonical command list and derive docs, required-command validation, and runtime execution from that source.

**Acceptance criteria**
- Command sequence shown in the page template, validation checks, and execution behavior are identical (order + flags).

---

## 4) Test-improvement task (P2)

**Issue**
- Existing tests verify happy-path score and artifact existence, but do not test the negative/contract semantics for the two weak checks above or for command-lane parity.

**Evidence**
- `tests/test_integration_expansion3_closeout.py`: `test_lane67_json` and `test_lane67_emit_pack_and_execute` focus on status + files, not check semantics.

**Proposed task**
- Add negative tests that intentionally remove top-10 markers and board anchors.
- Add a parity test that compares documented commands to emitted validation command docs.
- Add a text-hygiene assertion for malformed heading prefix (`#  `).

**Acceptance criteria**
- New tests fail on current implementation and pass only after bug/doc fixes are applied.

---

## Merge-finalization checklist

1. Land **Bug-fix task (P1)** first so score output regains trustworthy signal quality.
2. Land **Documentation discrepancy task (P2)** next to remove command-lane confusion before broad rollout.
3. Land **Test-improvement task (P2)** in the same PR as (1)/(2) or immediately after, so regressions are blocked.
4. Land **Typo-fix task (P3)** as a cleanup PR once semantic checks are stable.
