# Release-confidence examples

These examples are short proof scenarios you can run (or compare against) to understand what SDETKit's flagship workflow looks like in practice.

## Scenario 1: "Is this repo basically healthy?" (quick confidence pass)

**Situation**

You just cloned the repo and want a fast confidence signal before deeper checks.

**Command**

```bash
bash scripts/ready_to_use.sh quick
```

**Representative output**

```text
[3/4] Running CI quick lane...
ok: repo layout invariants hold
gate fast: OK
[OK] doctor (...) rc=0
[OK] ci_templates (...) rc=0
[OK] ruff (...) rc=0
[OK] mypy (...) rc=0
[OK] pytest (...) rc=0
[4/4] Quick mode complete.
Repository is ready to use.
```

**Maintainer next action**

Move to strict release mode when you need a higher-trust go/no-go decision.

---

## Scenario 2: "What blocks release?" (strict release gate fails)

**Situation**

You want release-level confidence. The gate should fail loudly if release prerequisites are not met.

**Command**

```bash
python -m sdetkit gate release
```

**Representative output**

```text
gate: problems found
gate release: FAIL
[FAIL] doctor_release rc=2
[OK] playbooks_validate rc=0
[OK] gate_fast rc=0
failed_steps:
- doctor_release
```

**Maintainer next action**

Run the failing check directly, fix the issue, and rerun the release gate.

```bash
python -m sdetkit doctor --release --format json
```

---

## Scenario 3: "Tune policy strictness" (security budget as release control)

**Situation**

You need to enforce security findings budgets in a transparent, machine-readable way.

**Commands**

```bash
# strict: fail if any info/warn/error findings appear
python -m sdetkit security enforce --format json --max-error 0 --max-warn 0 --max-info 0

# less strict: allow informational findings while keeping 0 errors/warnings
python -m sdetkit security enforce --format json --max-error 0 --max-warn 0 --max-info 200
```

**Representative output**

```json
{"counts":{"error":0,"info":131,"total":131,"warn":0},"ok":false,"exceeded":[{"metric":"info","count":131,"limit":0}]}
{"counts":{"error":0,"info":131,"total":131,"warn":0},"ok":true,"exceeded":[]}
```

**Maintainer next action**

Set thresholds per branch/stage (for example, stricter on release branches, looser on feature branches), then enforce the selected policy in CI.
