from __future__ import annotations

from pathlib import Path


def test_runtime_dockerfile_uses_sdetkit_entrypoint() -> None:
    dockerfile = Path("Dockerfile.runtime")
    assert dockerfile.exists()
    text = dockerfile.read_text(encoding="utf-8")
    assert 'ENTRYPOINT ["sdetkit"]' in text
    assert 'CMD ["--help"]' in text
    assert "python -m pip install --no-cache-dir ." in text
