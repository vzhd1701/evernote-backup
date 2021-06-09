from typing import Any, Callable, List

import click

DIR_ONLY = click.Path(
    file_okay=False,
    writable=True,
    resolve_path=True,
)

FILE_ONLY = click.Path(
    dir_okay=False,
    writable=True,
    resolve_path=True,
)


class NaturalOrderGroup(click.Group):
    def list_commands(self, ctx: Any) -> List[str]:
        return list(self.commands.keys())


def group_options(*options: Callable) -> Callable:
    def wrapper(function: Callable) -> Callable:
        for option in reversed(options):
            function = option(function)
        return function

    return wrapper
