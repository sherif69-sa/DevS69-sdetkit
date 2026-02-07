# Roadmap

This repo is a long-term SDET bootcamp project. The goal is to grow it into a practical toolkit + training track.

## Now (stabilize)

- Keep CI green (quality, pages, releases, mutation tests)
- Improve docs (examples, recipes, troubleshooting)
- Add more CLI examples and realistic test scenarios

## Next (features)

- `apiget`:
  - Better pagination strategies (cursor/offset/link-header recipes)
  - More observability hooks (trace/request-id)
  - More failure-mode tests (timeouts, retries, bad JSON, partial pages)
- `kv`:
  - More input edge cases and strict/relaxed modes

## Later (professional polish)

- More modules:
  - contract testing helpers
  - test data builders/factories
  - logging/metrics helpers
- More exercises:
  - kata tasks with progressive difficulty
  - mutation-test "killers" as training objectives

## Release plan

- v0.x: ship improvements frequently while APIs are still flexible
- v1.0: lock in stable CLI/API once patterns are proven
