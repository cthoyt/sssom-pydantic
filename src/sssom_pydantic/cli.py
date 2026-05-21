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
@click.option("--add-examples", is_flag=True, default=False, help="Add example SSSOM records.")
@click.option("--tab", is_flag=True)
@click.option("--host", type=str, default="0.0.0.0", show_default=True)  # noqa:S104
@click.option("--port", type=int, default=8876, show_default=True)
def web(add_examples: bool, tab: bool, host: str, port: int) -> None:
    """Run the web app (with SQL backend)."""
    import uvicorn

    from sssom_pydantic.web import get_app

    if tab:
        import webbrowser

        webbrowser.open_new_tab(f"http://{host}:{port}/docs")

    uvicorn.run(get_app(add_examples="builtin" if add_examples else None), host=host, port=port)


@main.command()
@click.option("source_prefix", required=True, type=Path)
@click.option("target_prefix", required=True, type=Path)
@click.option("input", required=True)
@click.option("output", required=True)
def filter(source_prefix: str, target_prefix: str | None, input: Path, output: Path) -> None:
    """Implement the filter workflow for a given prefix.

    $ sssom_pydantic filter


    """
    from curies.triples import (
        keep_predicates,
        keep_prefixes_both,
        keep_prefixes_either,
    )
    from curies.vocabulary import exact_match

    import sssom_pydantic
    from sssom_pydantic.process import (
        exclude_negative,
        exclude_unsure,
        invert_by_prefix_pair,
        invert_by_target_prefix,
    )

    mappings_list, converter, metadata = sssom_pydantic.read(input)

    mappings = exclude_negative(mappings_list)
    mappings = exclude_unsure(mappings)
    mappings = keep_predicates(mappings, exact_match)

    if target_prefix:
        mappings = keep_prefixes_both(mappings, {source_prefix, target_prefix})
        mappings = invert_by_prefix_pair(mappings, source_prefix, target_prefix)
    else:
        mappings = keep_prefixes_either(mappings, source_prefix)
        mappings = invert_by_target_prefix(mappings, source_prefix)

    sssom_pydantic.write(mappings, converter=converter, metadata=metadata, path=output)


if __name__ == "__main__":
    main()
