# Migration and backward compatibility note

## What changed

SDETKit now treats the canonical public/stable path as the first-time entry point:

- `python -m sdetkit gate fast`
- `python -m sdetkit gate release`
- `python -m sdetkit doctor`

Umbrella kits remain advanced but supported:

- `sdetkit kits ...`
- `sdetkit release ...`
- `sdetkit intelligence ...`
- `sdetkit integration ...`
- `sdetkit forensics ...`

## What did not change

Stable direct commands remain supported and unchanged as compatibility lanes:

- `gate`, `doctor`, `security`, `repo`, `evidence`, `report`, `policy`

## Practical migration guidance

- New scripts/docs: prefer kit routes.
- Existing CI scripts: no forced migration required.
- Gradual modernization: update discovery/help/docs first, then command paths over time.

## Experimental summary

Transition-era `dayNN-*` / `*-closeout` lanes remain available but are intentionally non-flagship.
Forensics remains production-usable with deterministic contracts while some sub-lanes may continue to evolve.
