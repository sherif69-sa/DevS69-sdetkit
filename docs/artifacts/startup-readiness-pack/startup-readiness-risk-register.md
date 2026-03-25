# Startup readiness risk register

| Risk | Trigger | Mitigation |
| --- | --- | --- |
| Docs drift | Required sections are removed | Run `startup-readiness --strict` in CI |
| Broken command examples | CLI flags change | Keep startup-readiness tests in startup fast-lane |
| Missing artifacts | Report generation skipped | Require artifact publish in weekly cadence |
