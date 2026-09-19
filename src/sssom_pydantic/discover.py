"""Discover SSSOM from GitHub."""

import click
import json

from pystow.github import search_code
import pystow
from pystow.utils import write_json

QUERY = "path:*.sssom.tsv -is:fork"


@click.command()
@click.option("--refresh", is_flag=True)
def main(refresh: bool) -> None:
    """Discover SSSOM from GitHub."""
    refresh = True
    path = pystow.join("sssom", name="github-search.json")
    if not path.is_file() or refresh:
        results = list(search_code(QUERY))
        write_json(results, path)
    else:
        results = json.loads(path.read_text())

    click.echo(str(results[0]))


if __name__ == '__main__':
    main()
