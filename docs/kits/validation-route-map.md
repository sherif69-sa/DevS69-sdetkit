# Validation route map

`sdetkit kits route-map` answers: "this dependency changed, what is the smallest command that proves the change is safe?"

```bash
python -m sdetkit kits route-map
python -m sdetkit kits route-map httpx --format json
python -m sdetkit kits route-map --impact-area docs
python -m sdetkit kits route-map --repo-usage-tier hot-path
```

Each match is a declared dependency (see [dependency radar](dependency-radar-dashboard.md) for how they are found) with:

| Field | Meaning |
| --- | --- |
| `package`, `spec`, `groups` | The dependency, its declared requirement and the groups that declare it. |
| `locked_version` | The version your lockfile pins, or `null`. |
| `repo_usage_tier` | `hot-path`, `balanced` or `edge`. |
| `repo_usage_files` | The repository's files that import it. |
| `test_files` | The test files among them that pytest collects (`test_*.py`, `*_test.py`). |
| `primary_validation` | The narrowest command, chosen in this order: `python -m pytest -q` with those test files when there are 10 or fewer; the whole suite (`python -m sdetkit gate fast --only pytest`) when there are more; `python -m sdetkit gate fast` when no test imports the package. |
| `alternate_validation` | The broader commands to escalate to. |

Run the `primary_validation` first, and escalate only when it shows risk. Filters work as for the radar: a query, `--impact-area` and `--repo-usage-tier`.
