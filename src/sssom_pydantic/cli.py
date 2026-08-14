"""Command line interface for :mod:`sssom_pydantic`."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import click

if TYPE_CHECKING:
    from .api import SemanticMapping
    from .contrib.owl import AxiomMode

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
MULTIPLE_INPUT_OPTION = click.option(
    "-i",
    "--input",
    multiple=True,
    help="Path to a local file or URL to a remote file",
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
@click.option(
    "--exclude-negative/--no-exclude-negative", "do_exclude_negative", is_flag=True, default=True
)
@click.option(
    "--exclude-unsure/--no-exclude-unsure", "do_exclude_unsure", is_flag=True, default=True
)
@click.option("--exclude-predicted", is_flag=True, default=True)
def subset(
    prefix: str,
    target_prefix: str | None,
    input: Path | None,
    output: Path | None,
    justification_policy: Literal["retain", "derive"],
    standardize: bool,
    do_exclude_negative: bool,
    do_exclude_unsure: bool,
    exclude_predicated: bool,
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

    mappings: Iterable[SemanticMapping]
    mappings, converter, metadata = sssom_pydantic.read(input or sys.stdin)

    if do_exclude_negative:
        mappings = exclude_negative(mappings)
    if do_exclude_unsure:
        mappings = exclude_unsure(mappings)
    if exclude_predicated:
        raise NotImplementedError
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
    help="If set, propagates annotations from mappings into OWL",
)
@click.option(
    "-d",
    "--declarations",
    is_flag=True,
    help="If set, adds declarations (and labels, when available)",
)
@click.option("--mode", type=click.Choice(["bridge", "inline"]), default="inline")
@click.option("--no-generation-comment", is_flag=True)
@click.option("--negation-workflow", is_flag=True)
def owl(
    input: Path | None,
    output: Path | None,
    cutoff: float,
    mapping_annotations: bool,
    declarations: bool,
    mode: AxiomMode,
    no_generation_comment: bool,
    negation_workflow: bool,
) -> None:
    """Convert SSSOM to OWL, serialized as Functional OWL (OFN)."""
    import sys

    import sssom_pydantic
    from sssom_pydantic.contrib.owl import write_owl

    mappings, converter, metadata = sssom_pydantic.read(input or sys.stdin)

    write_owl(
        mappings,
        output or sys.stdout,
        converter=converter,
        mode=mode,
        metadata=metadata,
        iri=str(metadata.id),
        minimum_confidence=cutoff,
        mapping_annotations=mapping_annotations,
        declarations=declarations,
        generation_comment=not no_generation_comment,
        negation_workflow=negation_workflow,
    )


@main.command(params=[p for p in owl.params if p.name != "mode"])
@click.pass_context
def bridge(context: click.Context, **kwargs: Any) -> None:
    """Convert SSSOM to OWL in bridge mode, serialized as Functional OWL (OFN)."""
    context.invoke(owl, mode="bridge", **kwargs)


def _default_iri() -> str:
    import uuid

    return f"https://example.org/{uuid.uuid4()}.sssom.tsv"


@main.command()
@MULTIPLE_INPUT_OPTION
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
    from sssom_pydantic import MappingSet, standardize_mappings
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


@main.command(name="compare")
@click.argument("left")
@click.argument("right")
@click.option(
    "--left-label",
    help="A short label for the left mapping set. If not given, falls "
    "back to the left mapping set title.",
)
@click.option(
    "--right-label",
    help="A short label for the right mapping set. If not given, falls "
    "back to the right mapping set title.",
)
@click.option(
    "--show-missing",
    is_flag=True,
    help="When the left and right mapping set don't both have the same mappings, "
    "should notes be shown in the output?",
)
@click.option(
    "--standardize-flip",
    is_flag=True,
    help="Should subject/object order be automatically standardized by lexicographical order? "
    "This is useful when combining arbitrary SSSOM files that might have curated with different "
    "subject and object rules.",
)
@OUTPUT_OPTION
@STANDARDIZE_FLAG
def compare_it(
    left: str,
    right: str,
    output: Path | None,
    standardize: bool,
    left_label: str | None,
    right_label: str | None,
    standardize_flip: bool,
    show_missing: bool,
) -> None:
    """Compare manual curations in two SSSOM files."""
    import sys

    import curies
    from pystow.utils import safe_write_text

    from .api import _get_preferred_converter, standardize_mappings
    from .compare import get_comparison_markdown
    from .io import read
    from .process import invert_on_unordered

    # define them as iterables to avoid confusion later
    left_mappings: Iterable[SemanticMapping]
    right_mappings: Iterable[SemanticMapping]

    left_mappings, left_converter, left_metadata = read(left)
    right_mappings, right_converter, right_metadata = read(right)

    if standardize:
        converter = _get_preferred_converter(left_converter, right_converter)
        left_mappings = standardize_mappings(left_mappings, converter=converter)
        right_mappings = standardize_mappings(right_mappings, converter=converter)
    else:
        converter = curies.chain([left_converter, right_converter])

    if standardize_flip:
        left_mappings = invert_on_unordered(left_mappings, converter=converter)
        right_mappings = invert_on_unordered(right_mappings, converter=converter)

    markdown = get_comparison_markdown(
        left_mappings,
        right_mappings,
        left_label=left_label or left_metadata.title,
        right_label=right_label or right_metadata.title,
        show_missing=show_missing,
    )
    safe_write_text(markdown, output or sys.stdout)
    if output:
        import os

        os.system(  # noqa:S605
            f"npx --yes prettier --check --log-level=silent --prose-wrap always --write {output}"
        )


@main.command(name="evaluate")
@MULTIPLE_INPUT_OPTION
@click.option("--accept-unspecified", is_flag=True)
@click.option("--tablefmt", default="github", show_default=True)
def evaluate(input: Iterable[str], accept_unspecified: bool, tablefmt: str) -> None:
    """Produce an evaluation of predicted mappings."""
    import itertools as itt

    import sssom_pydantic

    from .workflow.evaluation import evaluate_predictions, tabulate_evaluation

    parts = [sssom_pydantic.read(path) for path in input]
    mappings = itt.chain.from_iterable(part.mappings for part in parts)
    res = evaluate_predictions(mappings, accept_unspecified=accept_unspecified)
    click.echo(tabulate_evaluation(res, tablefmt=tablefmt))


if __name__ == "__main__":
    main()
