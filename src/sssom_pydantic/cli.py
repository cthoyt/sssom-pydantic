"""Command line interface for :mod:`sssom_pydantic`."""

import click

__all__ = [
    "main",
]


@click.command()
def main() -> None:
    """CLI for sssom_pydantic."""


if __name__ == "__main__":
    main()
