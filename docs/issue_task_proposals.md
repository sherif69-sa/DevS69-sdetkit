# Issue-driven task proposals (2026-04-25)

This note proposes four actionable tasks based on codebase review.

## 1) Typo task

**Issue:** The heading `## Lane command lane` repeats the word "lane" and reads like a typo/wording error.

**Evidence:** `docs/integrations-trust-assets-refresh-closeout.md`.

**Proposed task:**
- Rename `## Lane command lane` to `## Command lane` (or `## Lane command path`) to improve readability and consistency with other docs.

---

## 2) Bug-fix task

**Issue:** `build_trust_assets_refresh_closeout_summary` computes `board_has_distribution_scaling` using an empty string anchor (`""`). Because every string contains `""`, the anchor check is effectively always true whenever the board file exists, which can mask missing expected content.

**Evidence:** `src/sdetkit/evidence/trust_assets_refresh_closeout_75.py`.

**Proposed task:**
- Replace the empty anchor with a meaningful required phrase (for example, `"distribution scaling"` or a specific checklist line).
- Add a regression test that fails when the board is present but missing that required phrase.

---

## 3) Code comment / documentation discrepancy task

**Issue:** The default template embedded in code still contains placeholder-like blanks (`"#  — ..."`, `"## Why  matters"`, `"## Required inputs ()"`), while the checked-in docs page uses human-readable text (`"Lane"` placeholders resolved). The in-code default and published docs diverge.

**Evidence:**
- `src/sdetkit/evidence/trust_assets_refresh_closeout_75.py` (`_DEFAULT_PAGE_TEMPLATE`)
- `docs/integrations-trust-assets-refresh-closeout.md`

**Proposed task:**
- Update `_DEFAULT_PAGE_TEMPLATE` to match the intended rendered document structure/content.
- Add a lightweight contract check that rejects unresolved placeholder patterns like `"## Required inputs ()"`.

---

## 4) Test-improvement task

**Issue:** Existing lane 75 tests validate command success and artifacts, but they do not assert template hygiene (no unresolved placeholders / malformed headings), so broken default text can pass tests.

**Evidence:** `tests/test_trust_assets_refresh_closeout.py`.

**Proposed task:**
- Add explicit assertions that `_DEFAULT_PAGE_TEMPLATE` does **not** include unresolved patterns such as:
  - `"## Required inputs ()"`
  - `"## Why  matters"`
  - `"#  —"`
- Add a negative test for the board-anchor logic noted in the bug task.
