# n8n Integration (PR Webhook Automation)

This repository includes a GitHub-native PR quality workflow (`pr-quality-comment.yml`) that
runs `quality.sh cov` on PR open/update and posts a PR comment.

If you want an n8n production vibe, connect GitHub webhooks to n8n and mirror the same flow:

1. GitHub webhook (`pull_request` events) → n8n Webhook node.
2. n8n triggers a runner/container job that executes:
   - `python -m pip install -r requirements-test.txt -r requirements-docs.txt -e .`
   - `bash quality.sh cov`
3. n8n posts the result back using GitHub API:
   - commit status/check run
   - PR comment summary

## Minimal payload strategy

Use PR number, repo owner/name, head SHA, and workflow URL in your status/comment payload.

## Suggested comment template

```markdown
### SDET Quality Gate
- result: PASS/FAIL
- command: `bash quality.sh cov`
- details: <link to logs>
```

This keeps signal high and matches the same quick-feedback style as `sdetkit doctor --pr`.


## Example: gate on repository audit JSON

1. Add an Execute Command node:

```bash
sdetkit repo check --format json --out report.json --force
```

2. Add a Read Binary/File node to load `report.json`.
3. Add a Function node:

```javascript
const report = JSON.parse($json.data);
if (!report.summary.ok) {
  throw new Error(`Repo findings: ${report.summary.findings}`);
}
return [{ json: report.summary }];
```

This gives CI/n8n-friendly deterministic machine output.
