# AGENTS.md - Quality and Verification Rules for AI Coding Agents

All AI coding assistants (Gemini, Claude, Cursor, Codex) working in this repository MUST follow these invariants:

1. **Gate Fast First:**
   Before finalizing any turn, execute:
   ```bash
   python -m sdetkit gate fast
   ```
   All checks (lint, format, types, tests) must be green (`SHIP`).

2. **Verify Change Invariant:**
   Never remove, empty, or skip existing tests. Verify your working tree:
   ```bash
   python -m sdetkit verify change
   ```

3. **Safe Auto-Fix:**
   Do not introduce unasserted whitespace or formatting drift. Run:
   ```bash
   python -m sdetkit auto-fix --apply
   ```

4. **MCP Super-Bridge:**
   When connected via Model Context Protocol, utilize `verify_change`, `gate_fast`, `doctor`, `diagnose_failure`, `run_mutation`, and `auto_fix`.
