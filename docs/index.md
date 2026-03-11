<div class="hero-panel" markdown>

<div class="hero-badges" markdown>

<span class="pill">Release-confidence focused</span>
<span class="pill">Deterministic by design</span>
<span class="pill">Audit-friendly outputs</span>

</div>

# DevS69 SDETKit

SDETKit is a release confidence toolkit for SDET, QA, and DevOps teams that need a repeatable answer to: **"is this repo ready to ship?"**

<div class="hero-actions" markdown>

[Start in 5 minutes](#start-in-5-minutes){ .md-button .md-button--primary }
[Open quickstart](ready-to-use.md){ .md-button }
[Adopt in your repo](adoption.md){ .md-button }
[Adoption troubleshooting](adoption-troubleshooting.md){ .md-button }
[See examples](examples.md){ .md-button }
[See evidence commands](evidence.md){ .md-button }

</div>

</div>

## Start in 5 minutes

Run the flagship workflow:

```bash
bash scripts/ready_to_use.sh quick
```

Then run the stricter release gate:

```bash
bash scripts/ready_to_use.sh release
```

### What happens

1. Bootstrap a local environment.
2. Validate CLI health.
3. Run CI-style checks.
4. (Release mode) enforce security policy budgets and run the release gate.

### What proves value quickly

You get deterministic pass/fail output and a clear go/no-go signal you can reuse in local and CI workflows.

## Flagship workflow (manual form)

```bash
bash ci.sh quick --skip-docs
bash quality.sh cov
python -m sdetkit security enforce --format json --max-error 0 --max-warn 0 --max-info 0
python -m sdetkit gate release
```

## Who should start where

- **SDET / QA:** [Doctor](doctor.md) and [CLI](cli.md)
- **DevOps / platform:** [Production readiness](production-readiness.md) and [Security gate](security-gate.md)
- **Maintainers:** [Evidence](evidence.md) and [Releasing](releasing.md)

## Next steps

- [Ready-to-use quickstart](ready-to-use.md)
- [Adopt in your repository](adoption.md)
- [Adoption troubleshooting](adoption-troubleshooting.md)
- [Release-confidence examples](examples.md)
- [Repo tour](repo-tour.md)
- [First contribution quickstart](first-contribution-quickstart.md)
- [Contributing](contributing.md)
- [Full command reference](cli.md)
