import click
from click.testing import CliRunner

from evernote_backup.cli_app_click_util import DescribedChoice, DescribedChoiceCommand


def _make_described_cmd():
    @click.command(cls=DescribedChoiceCommand)
    @click.option(
        "--mode",
        type=click.Choice(["alpha", "beta"], case_sensitive=False),
        default="alpha",
        show_default=True,
        cls=DescribedChoice,
        choice_help={
            "alpha": "First mode description.",
            "beta": "Second mode description.",
        },
        help="Pick a mode.",
    )
    @click.option("--plain", help="A normal option.")
    def cmd(mode, plain):
        """Sample command."""
        click.echo(f"mode={mode};plain={plain}")

    return cmd


def test_described_choice_stores_choice_help():
    opt = DescribedChoice(
        ["--mode"],
        type=click.Choice(["a", "b"]),
        choice_help={"a": "help a", "b": "help b"},
    )

    assert opt.choice_help == {"a": "help a", "b": "help b"}


def test_described_choice_command_help_includes_choice_lines():
    runner = CliRunner()
    result = runner.invoke(_make_described_cmd(), ["--help"])

    assert result.exit_code == 0
    assert "--mode [alpha|beta]" in result.output
    assert "Pick a mode." in result.output
    assert "alpha" in result.output
    assert "First mode description." in result.output
    assert "beta" in result.output
    assert "Second mode description." in result.output
    assert "--plain" in result.output
    assert "A normal option." in result.output


def test_described_choice_command_help_indents_choice_names():
    runner = CliRunner()
    result = runner.invoke(_make_described_cmd(), ["--help"])

    # Choice rows are rendered with 4-space indent on the name column.
    assert "    alpha" in result.output
    assert "    beta" in result.output


def test_described_choice_command_parses_choice_value():
    runner = CliRunner()
    result = runner.invoke(_make_described_cmd(), ["--mode", "beta", "--plain", "x"])

    assert result.exit_code == 0
    assert result.output.strip() == "mode=beta;plain=x"


def test_described_choice_command_rejects_invalid_choice():
    runner = CliRunner()
    result = runner.invoke(_make_described_cmd(), ["--mode", "gamma"])

    assert result.exit_code != 0
    assert "Invalid value" in result.output


def test_described_choice_command_skips_hidden_options():
    @click.command(cls=DescribedChoiceCommand)
    @click.option("--visible", help="Shown in help.")
    @click.option("--secret", hidden=True, help="Hidden option.")
    def cmd(visible, secret):
        """pass"""

    runner = CliRunner()
    result = runner.invoke(cmd, ["--help"])

    assert result.exit_code == 0
    assert "--visible" in result.output
    assert "Shown in help." in result.output
    assert "--secret" not in result.output
    assert "Hidden option." not in result.output


def test_described_choice_command_without_custom_options_still_works():
    @click.command(cls=DescribedChoiceCommand)
    def cmd():
        """No custom options here."""

    runner = CliRunner()
    result = runner.invoke(cmd, ["--help"])

    assert result.exit_code == 0
    assert "No custom options here." in result.output
    assert "--help" in result.output
