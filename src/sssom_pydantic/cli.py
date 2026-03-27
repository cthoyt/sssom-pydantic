"""Command line interface for :mod:`sssom_pydantic`."""

from pathlib import Path

import click

__all__ = [
    "main",
]


@click.group()
def main() -> None:
    """CLI for sssom_pydantic."""


@main.command(name="format")
@click.argument("path", type=Path)
def format_sssom_tsv(path: Path) -> None:
    """Lint a SSSOM TSV file."""
    import sssom_pydantic

    sssom_pydantic.lint(path)


@main.command()
def web() -> None:
    """Run the web app (with SQL backend)."""
    import uvicorn

    from sssom_pydantic.web import get_app

    uvicorn.run(get_app(), host="0.0.0.0", port=8776)  # noqa:S104


if __name__ == "__main__":
    main()
