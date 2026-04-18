# Team use cases

This page shows practical ways teams use SDETKit in day-to-day delivery work, using the current public command surface (`gate fast`, `gate release`, `doctor`) and artifact-first triage.

Canonical artifact-producing run:

```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --out build/release-preflight.json
python -m sdetkit doctor
```

## 1) PR gate / pre-merge confidence

**When:** before merge on pull requests.

**What teams run:**

```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
```

**How teams use it:**
- Treat `build/gate-fast.json` as the first decision artifact.
- Check `ok` and `failed_steps` first, before reading raw logs.
- Keep the same command locally and in CI so a PR decision does not depend on who ran it.

**Outcome:** a deterministic pre-merge pass/fail signal with structured evidence for reviewers.

## 2) Release go/no-go

**When:** during release preflight and sign-off.

**What teams run:**

```bash
python -m sdetkit gate release --format json --out build/release-preflight.json
```

**How teams use it:**
- Use `build/release-preflight.json` as the top-level release decision input.
- Interpret `ok: true` as ready to advance and `ok: false` as no-go until remediated.
- Use `failed_steps` to identify the first deterministic remediation target.

**Outcome:** release decisions are based on one declared contract instead of ad hoc interpretation.

## 3) Repo onboarding / first triage

**When:** a new engineer or reviewer needs a fast understanding of repo readiness.

**What teams run:**

```bash
python -m sdetkit doctor
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --out build/release-preflight.json
```

**How teams use it:**
- `doctor` confirms environment and setup assumptions.
- `gate fast` gives quick readiness signals.
- `gate release` provides the release-oriented aggregate view.

**Outcome:** first triage is consistent across maintainers, newcomers, and CI.

## 4) Audit / evidence handoff

**When:** handing release readiness evidence between engineers, reviewers, and release owners.

**What teams hand off:**
- `build/gate-fast.json`
- `build/release-preflight.json`
- command invocation context from CI/local run logs

**How teams use it:**
- Reviewers validate decisions from machine-readable artifacts.
- Release owners can re-check the same fields without reconstructing ad hoc narratives.
- Teams store artifacts as evidence in PR/release records.

**Outcome:** handoff quality improves because decision inputs are explicit, repeatable, and parseable.
