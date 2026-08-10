"""DEMO."""

from pathlib import Path

import click
from curies.triples import keep_prefixes_both

import sssom_pydantic
from sssom_pydantic import SemanticMapping
from sssom_pydantic.compare import get_comparison_markdown
from sssom_pydantic.process import invert_by_prefix_pair

DEMO_RIGHT = "https://github.com/nfdi-de/section-metadata-wg-onto/raw/refs/heads/main/sssom/data/positive.sssom.tsv"
DEMO_RIGHT_NAME = "Charlie"
DEMO_LEFT = "https://github.com/NFDI4Chem/rsc-cmo/raw/refs/heads/Add-tsv-files/src/mappings/fix-mappings.sssom.tsv"
DEMO_LEFT_NAME = "Ambika"


@click.command()
@click.option("--left-url", default=DEMO_LEFT)
@click.option("--right-url", default=DEMO_RIGHT)
@click.option("--left-label", default=DEMO_LEFT_NAME)
@click.option("--right-label", default=DEMO_RIGHT_NAME)
@click.option("--output", type=Path)
def _demo(
    left_url: str, right_url: str, left_label: str, right_label: str, output: Path | None
) -> None:
    import sys

    import pystow
    from pystow.utils import safe_write_text

    module = pystow.module("tmp")

    target_prefix = "FIX"
    internal_cache_path = module.join(name=f"{target_prefix}-rsc.sssom.tsv")
    internal_mappings, internal_title = _do_it(left_url, internal_cache_path, target_prefix)
    external_cache_path = module.join(name=f"{target_prefix}-wg-onto.sssom.tsv")
    external_mappings, external_title = _do_it(right_url, external_cache_path, target_prefix)

    markdown = get_comparison_markdown(
        internal_mappings,
        external_mappings,
        left_label or internal_title or "left",
        right_label or external_title or "right",
    )
    import pyperclip

    pyperclip.copy(markdown)
    safe_write_text(markdown, output or sys.stdout)


def _do_it(o: str | Path, p: Path, target_prefix: str) -> tuple[list[SemanticMapping], str | None]:
    if p.is_file() and False:
        rr = sssom_pydantic.read(p)
        return rr.mappings, rr.mapping_set.title
    mappings_l, converter, metadata = sssom_pydantic.read(o)
    mappings = sssom_pydantic.standardize_mappings(mappings_l)
    mappings = keep_prefixes_both(mappings, {"CHMO", target_prefix})
    mappings = list(
        invert_by_prefix_pair(
            mappings,
            target_prefix,
            "CHMO",
            converter=converter,
        )
    )
    click.echo(f"got {len(mappings)} mappings for {target_prefix} from {o}")
    sssom_pydantic.write(mappings, p, converter=converter, metadata=metadata)
    return mappings, metadata.title


if __name__ == "__main__":
    _demo()
