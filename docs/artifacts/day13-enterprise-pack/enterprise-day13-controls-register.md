# Day 13 enterprise controls register

| Control area | Trigger | Mitigation |
| --- | --- | --- |
| Documentation drift | Required enterprise sections are removed | Run `enterprise-use-case --strict` in CI |
| Evidence gaps | Compliance artifacts are not published | Require `--execute --evidence-dir` in release pipeline |
| Policy baseline mismatch | Profile or control set changes unexpectedly | Run `sdetkit policy snapshot --output .sdetkit/day13-policy-snapshot.json` and diff against baseline |
