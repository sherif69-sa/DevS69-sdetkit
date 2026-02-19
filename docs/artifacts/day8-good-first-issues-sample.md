# Day 8 contributor funnel backlog

| ID | Title | Area | Estimate | Acceptance criteria |
| --- | --- | --- | --- | --- |
| `GFI-01` | Add --format markdown example for onboarding in README role table | docs | S | - README role-based onboarding section includes one markdown export example.<br>- Example command matches existing CLI flags and passes copy/paste validation.<br>- No broken links introduced in README/docs after update. |
| `GFI-02` | Add docs index quick link for day6 conversion QA sample | docs | S | - docs/index.md quick-jump section contains an anchor to Day 6 artifact guidance.<br>- Anchor resolves in rendered markdown.<br>- docs-qa command output remains clean for modified files. |
| `GFI-03` | Add one positive test for onboarding --platform windows payload | tests | S | - New test asserts windows setup snippet contains at least two actionable commands.<br>- Existing onboarding tests continue to pass.<br>- No production code behavior changes required. |
| `GFI-04` | Document weekly-review JSON schema fields in docs/cli.md | docs | S | - weekly-review section lists top-level keys produced by --format json.<br>- Field descriptions match current implementation names.<br>- Examples keep line lengths readable and consistent with docs style. |
| `GFI-05` | Add test covering docs-qa markdown formatter heading | tests | M | - Test verifies markdown output starts with expected Day 6 heading.<br>- Test includes at least one failing-link fixture and checks report summary counts.<br>- Test suite stays deterministic (no network calls). |
| `GFI-06` | Add contributor note for artifact naming convention | docs | S | - Contributing docs include explicit docs/artifacts/dayX-* naming guidance.<br>- Examples include at least one markdown artifact path.<br>- Language remains beginner-friendly and concise. |
| `GFI-07` | Add smoke test for sdetkit demo --format json output shape | tests | M | - Test asserts returned JSON includes name, steps, and hints keys.<br>- Test avoids executing shell commands (no --execute).<br>- Test passes on Linux CI environment. |
| `GFI-08` | Improve docs wording around strict mode in proof command | docs | S | - docs/cli.md explains strict-mode exit behavior in one short paragraph.<br>- Example includes strict usage for local + CI context.<br>- No contradictory language with day-3 report. |
| `GFI-09` | Add tiny helper test for weekly review recommendation count | tests | S | - Test asserts week-1 review includes exactly three next-week recommendations.<br>- Test uses existing repository fixture style.<br>- No snapshot files required. |
| `GFI-10` | Create docs snippet for running day contract scripts locally | docs | S | - Contributing or docs index includes a command block for day contract scripts.<br>- Snippet references at least day6 and day7 script examples.<br>- Instructions remain compatible with bash on Linux/macOS. |

## Day 8 execution notes

- Label each item as `good first issue` and include a mentoring contact in the issue body.
- Keep acceptance criteria testable so first-time contributors can self-validate before opening a PR.
- Prioritize docs + tests for the first cohort to reduce ramp-up risk.
