import json

from sdetkit import cli, proof


def test_proof_default_text_contains_steps(capsys):
    rc = proof.main([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Proof pack" in out
    assert "Doctor proof snapshot" in out
    assert "Repo audit proof snapshot" in out
    assert "Security proof snapshot" in out


def test_proof_json_machine_readable(capsys):
    rc = proof.main(["--format", "json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["name"] == "proof-pack"
    assert len(payload["steps"]) == 3


def test_cli_dispatches_proof(capsys):
    rc = cli.main(["proof", "--format", "text"])
    assert rc == 0
    assert "Proof tips" in capsys.readouterr().out


def test_proof_execute_strict_failure(monkeypatch, capsys):
    def fake_run(_command: str, _timeout: float):
        return 1, "", "boom", 0.1

    monkeypatch.setattr(proof, "_run_command", fake_run)
    rc = proof.main(["--execute", "--strict", "--format", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert all(item["status"] == "fail" for item in payload["execution"])
