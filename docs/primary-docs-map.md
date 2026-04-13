# Primary docs map (hard-limit view)

This map keeps top-level onboarding/navigation focused on one primary page per core intent:

1. **Start page**: [Start Here in 5 Minutes](start-here-5-minutes.md)
2. **CI path page**: [Recommended CI flow](recommended-ci-flow.md)
3. **Troubleshooting funnel**: [First failure triage](first-failure-triage.md)

## Guard command

Validate this mapping stays present and linked from `docs/index.md`:

```bash
python scripts/check_primary_docs_map.py --format json
```
