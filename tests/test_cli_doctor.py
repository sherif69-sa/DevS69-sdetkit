import json

from sdetkit import cli


def test_doctor_json_smoke(capsys):
    rc = cli.main(["doctor", "--json"])
    out = capsys.readouterr().out.strip()
    data = json.loads(out)

    assert rc in (0, 1)
    assert "python" in data and "version" in data["python"]
    assert "package" in data and data["package"]["name"] == "sdetkit"
    assert "missing" in data and isinstance(data["missing"], list)


def test_doctor_dev_tools_present_in_ci(capsys):
    rc = cli.main(["doctor", "--json", "--dev"])
    out = capsys.readouterr().out.strip()
    data = json.loads(out)

    assert rc == 0
    assert data["missing"] == []
    assert "tools" in data
    assert "pytest" in data["tools"]
