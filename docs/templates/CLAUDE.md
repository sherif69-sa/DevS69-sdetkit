# SDETKit Agent Instructions for Claude Code

## Verification Protocol
Before committing code or opening a pull request, run the native SDETKit verification:

1. **Verify Change (Zero Test Regression):**
   ```bash
   python -m sdetkit verify change
   ```
   Or invoke the MCP tool `verify_change`. Ensure status is `VERIFIED`.

2. **Fast Quality Gate:**
   ```bash
   python -m sdetkit gate fast
   ```
   Or invoke the MCP tool `gate_fast`. Ensure verdict is `SHIP`.

3. **Assertion Mutation Coverage:**
   ```bash
   python -m sdetkit verify mutation
   ```
   Or invoke the MCP tool `run_mutation` to ensure new logic has strong assertions.

4. **Safe Automated Remediation:**
   ```bash
   python -m sdetkit auto-fix --apply
   ```
   If formatting drift or ruff-fixable lint is detected.

5. **360-Degree Quality Cockpit:**
   ```bash
   python -m sdetkit cockpit
   ```
