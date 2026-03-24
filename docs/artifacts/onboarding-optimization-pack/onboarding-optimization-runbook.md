# Name 24 time-to-first-success runbook

1. Run `python -m sdetkit onboarding --platform all --format text`.
2. Run `python -m sdetkit onboarding-optimization --format json --strict`.
3. Emit the Name 24 pack and attach it to release readiness notes.
4. Capture first-success timing and keep the median below three minutes.
