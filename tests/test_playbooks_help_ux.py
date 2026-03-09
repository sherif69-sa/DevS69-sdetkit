import pytest

from sdetkit import playbooks_cli


def test_playbooks_help_describes_surface(capsys):
    with pytest.raises(SystemExit) as excinfo:
        playbooks_cli.main(["--help"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "Discover, run, and validate recommended playbooks and incubator workflows." in out
    assert "list" in out
    assert "run" in out
    assert "validate" in out


def test_playbooks_list_help_describes_catalog_filters(capsys):
    with pytest.raises(SystemExit) as excinfo:
        playbooks_cli.main(["list", "--help"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "List recommended playbooks, incubator workflows, and aliases." in out
    assert "--recommended" in out
    assert "--legacy" in out
    assert "--aliases" in out
    assert "--search SEARCH" in out


def test_playbooks_validate_help_describes_scope_controls(capsys):
    with pytest.raises(SystemExit) as excinfo:
        playbooks_cli.main(["validate", "--help"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "Validate that selected playbooks are importable and expose callable main()." in out
    assert "--recommended" in out
    assert "--legacy" in out
    assert "--aliases" in out
    assert "--all" in out
