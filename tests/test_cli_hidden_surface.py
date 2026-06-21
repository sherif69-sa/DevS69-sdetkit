from sdetkit import cli

HIDDEN_ADOPTION_LEARNING_COMMANDS = (
    "adoption-learning-report",
    "adoption-real-world-learning-matrix",
)


def test_root_help_hides_commands_by_default() -> None:
    help_text = cli._build_root_parser()[0].format_help()
    assert "docs-qa" not in help_text
    assert "proof" not in help_text
    for command in HIDDEN_ADOPTION_LEARNING_COMMANDS:
        assert command not in help_text


def test_root_help_can_show_hidden_commands() -> None:
    help_text = cli._build_root_parser(show_hidden_commands=True)[0].format_help()
    assert "docs-qa" in help_text
    assert "proof" in help_text
    assert "--show-hidden" in help_text
    for command in HIDDEN_ADOPTION_LEARNING_COMMANDS:
        assert command in help_text


def test_hidden_adoption_learning_commands_keep_direct_help(capsys) -> None:
    for command in HIDDEN_ADOPTION_LEARNING_COMMANDS:
        parser = cli._build_root_parser()[0]

        try:
            parser.parse_args([command, "--help"])
        except SystemExit as exc:
            assert exc.code == 0
        else:
            raise AssertionError(f"{command} --help did not exit")

        help_text = capsys.readouterr().out
        assert "usage:" in help_text
        assert command in help_text


def test_root_playbooks_command_dispatches_to_playbooks_surface(capsys) -> None:
    rc = cli.main(["playbooks", "list", "--recommended", "--format", "json"])
    assert rc == 0
    out = capsys.readouterr().out
    assert '"recommended"' in out


def test_root_playbooks_no_args_lists_catalog(capsys) -> None:
    rc = cli.main(["playbooks"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Recommended playbooks:" in out
