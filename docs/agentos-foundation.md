# AgentOS foundation

`sdetkit agent` includes a deterministic multi-agent orchestrator with **Manager + Workers + Reviewer** roles, safety gates, and provider-call caching.

## Orchestrator model

`agent run` uses a fixed execution loop:

1. **Manager** creates a plan.
   - In `provider.type=none`, planning is fully deterministic and rule-based.
   - In `provider.type=local`, manager and reviewer notes come from the local provider.
2. **Workers** execute planned actions.
   - Multiple workers are modeled explicitly (`worker-1`, `worker-2`) and assigned work round-robin.
   - Execution is sequential today, but structure is ready for parallel worker scheduling.
3. **Reviewer** validates worker outputs.
   - Any denied or failed action causes reviewer rejection and a non-zero status.
4. **Finalize** with canonical, stable run records saved to history.

## Budgets

`budgets.max_steps` and `budgets.max_actions` bound orchestration work.

- `max_actions` limits generated action count.
- `max_steps` limits total manager/worker/reviewer loop progression.
- `token_budget` is reserved for provider-aware future expansion.

## Safety gates

Dangerous actions require approval:

- `shell.run` is always gated.
- `fs.write` is gated when writing outside `.sdetkit/agent/workdir`.

CLI behavior:

- Default: interactive approval prompt on TTY; denial in non-interactive mode.
- `--approve`: auto-approve dangerous actions (recommended for CI/tests).

All denials are recorded in run records with explicit reason fields.

## Caching

Provider calls are cached by hashed request payload (`role + task + context`).

CLI flags:

- `--cache-dir .sdetkit/agent/cache` (default)
- `--no-cache` to disable provider cache reads/writes

This improves deterministic behavior and repeatability for local-provider runs.

## Commands

- `sdetkit agent init`
  - Creates `.sdetkit/agent/config.yaml`
  - Creates `.sdetkit/agent/history/`, `.sdetkit/agent/workdir/`, `.sdetkit/agent/cache/`
- `sdetkit agent run "<task>" [--approve] [--cache-dir <dir>] [--no-cache]`
  - Runs manager/worker/reviewer flow and writes canonical run history
- `sdetkit agent doctor`
  - Validates config, provider mode, budgets, and safety allowlists
- `sdetkit agent history`
  - Lists recent recorded runs

## Config (`.sdetkit/agent/config.yaml`)

```yaml
roles:
  manager: planner
  worker: executor
  reviewer: verifier
budgets:
  max_steps: 8
  max_actions: 4
  token_budget: 0
provider:
  type: none
  endpoint: http://127.0.0.1:11434/api/generate
  model: llama3
safety:
  write_allowlist:
    - .sdetkit/agent/workdir
  shell_allowlist:
    - python
```

Provider modes:

- `provider.type: none` — deterministic no-LLM mode (offline-first)
- `provider.type: local` — local HTTP provider integration
