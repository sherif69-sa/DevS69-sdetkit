# sdetkit

![tests](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/ci.yml/badge.svg)
![lint](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/lint.yml/badge.svg)


Small utilities for SDET-style exercises:

- `sdetkit.kvcli`: CLI that reads key=value pairs from stdin / --text / --path and prints JSON.
- `sdetkit.atomicio`: atomic write helper.
- `sdetkit.apiclient`: tiny JSON fetch helpers (sync + async).
- `sdetkit.textutil`: parsing utilities.

Quality gates:
- pytest
- 100% line coverage
- mutmut (mutation testing)
