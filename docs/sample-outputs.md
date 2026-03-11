# Sample outputs (representative first-run evidence)

Need a compact “what this artifact means and what to do next” map? See [CI artifact walkthrough](ci-artifact-walkthrough.md).

Use this page to quickly see what a **realistic first run** can look like on the Stable/Core path.

These snippets are **representative/illustrative** and based on documented outputs already used in this repository (not customer production screenshots).

## 1) Quick confidence run: `gate fast` succeeds

**Command**

```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
```

**Illustrative output snippet (pass shape)**

```json
{
  "failed_steps": [],
  "ok": true,
  "profile": "fast"
}
```

**What to notice**

- `ok: true` and empty `failed_steps` means the fast gate is green.
- `profile: "fast"` confirms this is the quick-confidence lane artifact.

**What to do next**

- Keep `gate fast` on PRs.
- Add strict security enforcement next on release branches:

```bash
python -m sdetkit security enforce --format json --max-error 0 --max-warn 0 --max-info 0 --out build/security-enforce.json
```

## 2) First strict security run: budget fails

**Command**

```bash
python -m sdetkit security enforce --format json --max-error 0 --max-warn 0 --max-info 0
```

**Representative output snippet**

```json
{"counts":{"error":0,"info":131,"total":131,"warn":0},"ok":false,"exceeded":[{"metric":"info","count":131,"limit":0}]}
```

**What to notice**

- `ok: false` with `exceeded` tells you exactly which budget blocked the gate.
- In first adoption, this is common and expected when `--max-info 0` is too strict for current baseline.

**What to do next**

- Keep `--max-error 0 --max-warn 0` strict.
- Set a temporary realistic `--max-info` baseline and ratchet down:

```bash
python -m sdetkit security enforce --format json --max-error 0 --max-warn 0 --max-info 200
```

## 3) Release-confidence evidence artifact: release readiness summary

**Command path**

```bash
python -m sdetkit gate release --format json --out build/release-preflight.json
```

**Representative evidence snippet**

```json
{
  "name": "day19-release-readiness-board",
  "summary": {
    "gate_status": "pass",
    "release_score": 96.56,
    "strict_all_green": true
  },
  "strict_failures": []
}
```

**What to notice**

- A compact summary can be used as release-review evidence (`gate_status`, score, strict-failure list).
- `strict_failures: []` indicates no strict blockers in this sample.

**What to do next**

- Upload release JSON artifacts in CI and link them in release decisions.
- If release fails, triage in order: `failed_steps` -> `doctor --release` -> rerun `gate release`.

## Related guides

- [Ready-to-use setup](ready-to-use.md)
- [Adopt SDETKit in your repository](adoption.md)
- [Release confidence with SDETKit](release-confidence.md)
- [First-failure triage](first-failure-triage.md)
- [Evidence showcase](evidence-showcase.md)
