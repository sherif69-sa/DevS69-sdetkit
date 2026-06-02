from pathlib import Path

from sdetkit import format_before_proof


def test_format_before_proof_normalizes_trailing_whitespace_and_final_newline() -> None:
    text = "alpha   \n\nbeta\t"
    assert format_before_proof.normalize_text(text) == "alpha\n\nbeta\n"


def test_format_before_proof_updates_text_file_without_authority_claims(tmp_path: Path) -> None:
    target = tmp_path / "sample.py"
    target.write_text("value = 1   ", encoding="utf-8")

    changed = format_before_proof.normalize_file(target)

    assert changed is True
    assert target.read_text(encoding="utf-8") == "value = 1\n"


def test_makefile_exposes_explicit_format_before_proof_workflow() -> None:
    makefile = Path("Makefile").read_text(encoding="utf-8")

    assert "format-before-proof: venv" in makefile
    assert "proof-after-format: format-before-proof" in makefile
    assert "python -m sdetkit.format_before_proof --root ." in makefile
    assert "python -m pre_commit run -a" in makefile
