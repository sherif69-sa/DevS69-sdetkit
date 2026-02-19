# Day 12 startup risk register

| Risk | Trigger | Mitigation |
| --- | --- | --- |
| Docs drift | Required sections are removed | Run `startup-use-case --strict` in CI |
| Broken command examples | CLI flags change | Keep Day 12 tests in startup fast-lane |
| Missing artifacts | Report generation skipped | Require artifact publish in weekly cadence |
