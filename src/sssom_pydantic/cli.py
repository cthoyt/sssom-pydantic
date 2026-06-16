"""Command line interface for :mod:`sssom_pydantic`."""

from collections.abc import Iterable
from pathlib import Path
from typing import Literal

import click

__all__ = [
    "main",
]


@click.group()
def main() -> None:
    """CLI for sssom_pydantic."""


STANDARDIZE_FLAG = click.option(
    "--standardize",
    is_flag=True,
    help="Standardize against Bioregistry preferred CURIE prefixes and (RDF) URI prefixes",
)
RELABEL_FLAG = click.option(
    "--relabel",
    is_flag=True,
    help="Re-label all subjects and objects using PyOBO",
)

INPUT_OPTION = click.option(
    "-i",
    "--input",
    help="Path to a local file or URL to a remote file. If not given, will get input from STDIN",
)
OUTPUT_OPTION = click.option(
    "-o",
    "--output",
    type=Path,
    help="Path to a local file to output. If not given, will write to STDOUT",
)


@main.command(name="format")
@click.argument("path", type=Path)
@STANDARDIZE_FLAG
@RELABEL_FLAG
@click.option("--drop-duplicates", is_flag=True)
def format_sssom_tsv(path: Path, standardize: bool, relabel: bool, drop_duplicates: bool) -> None:
    """Lint a SSSOM TSV file."""
    import sssom_pydantic

    sssom_pydantic.format(
        path, standardize=standardize, relabel=relabel, drop_duplicates=drop_duplicates
    )


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
@click.option(
    "-p",
    "--prefix",
    required=True,
    help="The prefix that becomes the subjects of all mappings. If used in combination with "
    "--standardize, will get automatically standardized.",
)
@click.option(
    "--target-prefix",
    help="The prefix that becomes the object of all mappings. If used in combination with "
    "--standardize, will get automatically standardized.",
)
@INPUT_OPTION
@OUTPUT_OPTION
@click.option(
    "--justification-policy",
    is_flag=True,
    type=click.Choice(["retain", "derive"]),
    default="retain",
    help="When inverting mappings, should the justification be derived to semapv:MappingInversion "
    "and reference be made back to the original mapping, or should the original jusitication be "
    "retained?",
)
@STANDARDIZE_FLAG
def subset(
    prefix: str,
    target_prefix: str | None,
    input: Path | None,
    output: Path | None,
    justification_policy: Literal["retain", "derive"],
    standardize: bool,
) -> None:
    """Implement the filter workflow for a given prefix.

    This workflow removes negative mappings, unsure mappings, and non-exact mappings.
    """
    import sys

    from curies.triples import keep_predicates, keep_prefixes_both, keep_prefixes_either
    from curies.vocabulary import exact_match

    import sssom_pydantic
    from sssom_pydantic import standardize_mappings
    from sssom_pydantic.api import _get_preferred_converter
    from sssom_pydantic.process import (
        exclude_negative,
        exclude_unsure,
        invert_by_object_prefix,
        invert_by_prefix_pair,
    )

    mappings_list, converter, metadata = sssom_pydantic.read(input or sys.stdin)

    mappings = exclude_negative(mappings_list)
    mappings = exclude_unsure(mappings)
    mappings = keep_predicates(mappings, exact_match)

    if standardize:
        converter = _get_preferred_converter(converter)
        mappings = standardize_mappings(mappings, converter=converter)

    prefix = converter.standardize_prefix(prefix, strict=True)

    if target_prefix is not None:
        target_prefix = converter.standardize_prefix(target_prefix, strict=True)
        mappings = keep_prefixes_both(mappings, {prefix, target_prefix})
        mappings = invert_by_prefix_pair(
            mappings,
            target_prefix,
            prefix,
            converter=converter,
            justification_policy=justification_policy,
        )
    else:
        mappings = keep_prefixes_either(mappings, prefix)
        mappings = invert_by_object_prefix(
            mappings, prefix, converter=converter, justification_policy=justification_policy
        )

    sssom_pydantic.write(mappings, output or sys.stdout, converter=converter, metadata=metadata)


@main.command()
@INPUT_OPTION
@OUTPUT_OPTION
@click.option(
    "--cutoff",
    type=float,
    help="Minimum confidence cutoff. Mappings w/o confidence are assumed to have 1.0 confidence",
)
@click.option(
    "-a",
    "--mapping-annotations",
    is_flag=True,
    help="If set, propagates annotations from mappings into bridge",
)
@click.option(
    "-d",
    "--declarations",
    is_flag=True,
    help="If set, adds declarations (and labels, when available)",
)
def bridge(
    input: Path | None,
    output: Path | None,
    cutoff: float,
    mapping_annotations: bool,
    declarations: bool,
) -> None:
    """Write OWL bridge axioms in Functional OWL (OFN)."""
    import sys

    import sssom_pydantic
    from sssom_pydantic.contrib.owl_bridge import write_owl_bridge

    mappings, converter, metadata = sssom_pydantic.read(input or sys.stdin)

    write_owl_bridge(
        mappings,
        output or sys.stdout,
        converter=converter,
        metadata=metadata,
        iri=str(metadata.id),
        minimum_confidence=cutoff,
        mapping_annotations=mapping_annotations,
        declarations=declarations,
    )


def _default_iri() -> str:
    import uuid

    return f"https://example.org/{uuid.uuid4()}.sssom.tsv"


@main.command()
@click.option(
    "-i",
    "--input",
    multiple=True,
    help="Path to a local file or URL to a remote file",
)
@OUTPUT_OPTION
@click.option("--mapping-set-id", default=_default_iri, help="The ID for the merged mapping set")
@click.option(
    "--mapping-set-title",
    default="Merged Mapping Sets",
    help="The title for the merged mapping set",
)
@click.option("--merge-manual", is_flag=True)
@STANDARDIZE_FLAG
def merge(
    input: Iterable[str],
    output: Path | None,
    merge_manual: bool,
    standardize: bool,
    mapping_set_title: str,
    mapping_set_id: str,
) -> None:
    """Merge SSSOM documents."""
    import itertools as itt
    import sys

    import curies
    from pydantic import AnyUrl

    import sssom_pydantic
    from sssom_pydantic import MappingSet, SemanticMapping, standardize_mappings
    from sssom_pydantic import process as pr
    from sssom_pydantic.api import _get_preferred_converter

    parts = [sssom_pydantic.read(path) for path in input]
    metadata = MappingSet(
        id=AnyUrl(mapping_set_id),
        title=mapping_set_title,
        source=[part.mapping_set.id for part in parts],
    )

    converter = curies.chain([part.converter for part in parts])
    mappings: Iterable[SemanticMapping] = itt.chain.from_iterable(part.mappings for part in parts)

    if standardize:
        converter = _get_preferred_converter(converter)
        mappings = standardize_mappings(mappings, converter=converter)

    if merge_manual:
        mappings = pr.merge_manual_curations(mappings, converter=converter)

    sssom_pydantic.write(
        mappings, output or sys.stdout, converter=converter, metadata=metadata, sort=True
    )


if __name__ == "__main__":
    main()
