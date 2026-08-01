import pathlib
from typing import Any, Callable

import click

DIR_ONLY = click.Path(
    file_okay=False,
    writable=True,
    resolve_path=True,
    path_type=pathlib.Path,
)

FILE_ONLY = click.Path(
    dir_okay=False,
    writable=True,
    resolve_path=True,
    path_type=pathlib.Path,
)


class NaturalOrderGroup(click.Group):
    def list_commands(self, ctx: Any) -> list[str]:
        return list(self.commands.keys())


class DescribedChoice(click.Option):
    """A Choice option whose choices get indented, aligned help lines."""

    def __init__(self, *args, choice_help: dict[str, str], **kwargs):
        self.choice_help = choice_help
        super().__init__(*args, **kwargs)


class DescribedChoiceCommand(click.Command):
    """Command that inlines DescribedChoice per-choice help under the option."""

    def format_options(self, ctx, formatter):
        rows = []
        for param in self.get_params(ctx):
            record = param.get_help_record(ctx)
            if record is None:
                continue
            rows.append(record)
            if isinstance(param, DescribedChoice):
                for choice, text in param.choice_help.items():
                    rows.append((f"    {choice}", text))
        if rows:
            with formatter.section("Options"):
                formatter.write_dl(rows)


def group_options(*options: Callable) -> Callable:
    def wrapper(function: Callable) -> Callable:
        for option in reversed(options):
            function = option(function)
        return function

    return wrapper
