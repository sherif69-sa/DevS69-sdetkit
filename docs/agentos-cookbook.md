# AgentOS cookbook

This page provides practical, deterministic recipes for `provider.type=none` workflows.

## Recipe 1: bootstrap AgentOS workspace

Command:

```bash
sdetkit agent init
```

Expected output:

- JSON with `created` entries.
- `.sdetkit/agent/config.yaml` and standard folders.

Artifacts:

- `.sdetkit/agent/config.yaml`
- `.sdetkit/agent/history/`
- `.sdetkit/agent/workdir/`
- `.sdetkit/agent/cache/`

## Recipe 2: run deterministic task

Command:

```bash
sdetkit agent run "action repo.audit {\"profile\":\"default\"}" --approve
```

Expected output:

- JSON record containing `status`, `steps`, `actions`, and stable `hash`.

Artifacts:

- `.sdetkit/agent/history/<hash>.json`

## Recipe 3: run automation template with overrides

Command:

```bash
sdetkit agent templates run report-dashboard --set profile=default --output-dir .sdetkit/agent/template-runs/report-dashboard
```

Expected output:

- JSON run record with `status=ok` and `artifacts` list.

Artifacts:

- `.sdetkit/agent/template-runs/report-dashboard/run-record.json`
- Any template-declared outputs.

## Recipe 4: build dashboard and markdown summary

Command:

```bash
sdetkit agent dashboard build --history-dir .sdetkit/agent/history --format html --output .sdetkit/agent/workdir/agent-dashboard.html --summary-output .sdetkit/agent/workdir/agent-summary.md
```

Expected output:

- JSON with `status=ok`, `output`, and run counts.

Artifacts:

- `.sdetkit/agent/workdir/agent-dashboard.html`
- `.sdetkit/agent/workdir/agent-summary.md`

## Recipe 5: export history summary CSV

Command:

```bash
sdetkit agent history export --history-dir .sdetkit/agent/history --format csv --output .sdetkit/agent/workdir/history-summary.csv
```

Expected output:

- JSON with `count` and `output`.

Artifacts:

- `.sdetkit/agent/workdir/history-summary.csv`

## Recipe 6: webhook ingest simulation (generic)

Command:

```bash
sdetkit agent serve --host 127.0.0.1 --port 8787
curl -sS -X POST http://127.0.0.1:8787/webhook/generic -H 'content-type: application/json' -d '{"channel":"slack","user_id":"u1","text":"audit status"}'
```

Expected output:

- HTTP 200 response with `status=ok` or `rate_limited`.

Artifacts:

- `.sdetkit/agent/conversations/slack/u1.jsonl`
- `.sdetkit/agent/rate_limits/slack/u1.json`

## Recipe 7: inspect cache behavior

Command:

```bash
sdetkit agent run "health-check" --cache-dir .sdetkit/agent/cache
sdetkit agent run "health-check" --cache-dir .sdetkit/agent/cache
```

Expected output:

- Same deterministic plan and same run hash in `provider=none` mode.

Artifacts:

- `.sdetkit/agent/cache/*.json`

## Recipe 8: approval gates in CI/non-interactive mode

Command:

```bash
sdetkit agent run 'action shell.run {"cmd":"python -V"}'
```

Expected output:

- Action denied with reason containing `approval required (non-interactive)`.

Artifacts:

- Denied action captured in history run record.

## Common mistakes and fixes

- Wrong config path:
  - Symptom: `agent error: [Errno 2] ... config.yaml`
  - Fix: pass `--config .sdetkit/agent/config.yaml` or run `sdetkit agent init` first.
- Unsafe write blocked:
  - Symptom: `write denied by allowlist`
  - Fix: write under `.sdetkit/agent/workdir` or update config allowlist intentionally.
- Missing history:
  - Symptom: empty dashboard/history results.
  - Fix: run `sdetkit agent run ...` at least once before dashboard/export.
- Invalid template schema:
  - Symptom: `agent error: ... metadata must be a mapping` (or similar).
  - Fix: validate template keys (`metadata`, `inputs`, `workflow`) and indentation.
- Server port in use:
  - Symptom: bind failure on `agent serve`.
  - Fix: switch to another port with `--port 8788`.
