# Determinism checklist

Use this checklist for local and CI-safe changes:

- Use stable ordering for rendered lists/maps (`sorted(...)`, stable key ordering in JSON output).
- Seed or monkeypatch randomness in tests (`random.random`, UUID/time sources) when behavior depends on it.
- Use LF (`\n`) newlines for generated text artifacts and patches.
- Keep tests offline by default; network tests must be explicitly marked (`@pytest.mark.network`) and are skipped by default.
- Avoid time-based sleeps in tests. Inject a fake sleep callback and assert calls instead.
- Prefer temp directories (`tmp_path`) and explicit fixtures over shared mutable state.
