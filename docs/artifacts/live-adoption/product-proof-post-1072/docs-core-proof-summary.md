# Docs core proof summary

- HEAD: `f30ef8e4a96df4d81d921a7040b966b7ebd63c4f`
- Decision: `SHIP`

| Metric | Count |
|---|---:|
| steps_total | 16 |
| failed_count | 0 |

## Steps

| Step | RC | OK | JSON valid | Command |
|---|---:|---:|---:|---|
| `agent-help` | 0 | `True` | `None` | `python -m sdetkit agent --help` |
| `doctor-json` | 0 | `True` | `None` | `python -m sdetkit doctor --format json --out build/live-adoption/docs-core-proof-post-review-fix-20260430T094237Z/doctor.json` |
| `evidence-help` | 0 | `True` | `None` | `python -m sdetkit evidence --help` |
| `gate-fast-json` | 0 | `True` | `None` | `python -m sdetkit gate fast --format json --stable-json --out build/live-adoption/docs-core-proof-post-review-fix-20260430T094237Z/gate-fast.json` |
| `gate-release-dry-run` | 0 | `True` | `None` | `python -m sdetkit gate release --format json --out build/live-adoption/docs-core-proof-post-review-fix-20260430T094237Z/release-preflight.json --dry-run` |
| `kits-list` | 0 | `True` | `None` | `python -m sdetkit kits list` |
| `notify-telegram-dry-run` | 0 | `True` | `None` | `python -m sdetkit notify telegram --message hello --dry-run` |
| `playbooks-aliases` | 0 | `True` | `None` | `python -m sdetkit playbooks validate --format json --aliases` |
| `playbooks-all` | 0 | `True` | `None` | `python -m sdetkit playbooks validate --format json --all` |
| `repo-help` | 0 | `True` | `None` | `python -m sdetkit repo --help` |
| `report-help` | 0 | `True` | `None` | `python -m sdetkit report --help` |
| `review-json` | 2 | `True` | `True` | `python -m sdetkit review . --no-workspace --format json` |
| `review-operator-json` | 2 | `True` | `True` | `python -m sdetkit review . --no-workspace --format operator-json` |
| `security-help` | 0 | `True` | `None` | `python -m sdetkit security --help` |
| `serve-help` | 0 | `True` | `None` | `python -m sdetkit serve --help` |
| `top-help` | 0 | `True` | `None` | `python -m sdetkit --help` |
