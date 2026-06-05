"""Compare semantic mappings.

.. code-block:: console

    $ sssom_pydantic subset -i https://github.com/nfdi-de/section-metadata-wg-onto/raw/refs/heads/main/sssom/data/positive.sssom.tsv \
        --prefix CHMO \
        --target-prefix FIX \
        --standardize \
        --output nfdi-chmo-fix.sssom.tsv
    $ python -m sssom_pydantic.compare \
        https://github.com/NFDI4Chem/rsc-cmo/raw/refs/heads/Add-tsv-files/src/mappings/fix-mappings.sssom.tsv \
        nfdi-chmo-fix.sssom.tsv \
        --left-label Ambika
        --right-label Charlie
"""  # noqa:E501

import io
from collections import defaultdict
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING, Literal

import click
from curies.triples import keep_prefixes_both
from curies.vocabulary import manual_mapping_curation
from tabulate import tabulate

import sssom_pydantic
from sssom_pydantic import SemanticMapping
from sssom_pydantic.process import invert_by_prefix_pair

if TYPE_CHECKING:
    import matplotlib.figure

__all__ = ["compare"]


def compare(
    left_mappings: list[SemanticMapping],
    right_mappings: list[SemanticMapping],
    left_label: str,
    right_label: str,
    venn_type: Literal["svg", "mermaid"] | None = None,
) -> str:
    """Compare two sets of mappings.

    :param left_mappings: left mappings
    :param right_mappings: right mappings
    :param left_label: The label for the left mapping source
    :param right_label: The label for the right mapping source
    :param venn_type: The mechanism for producing a venn diagram
    """
    if venn_type is None:
        venn_type = "mermaid"
    left_mappings = [m for m in left_mappings if m.justification == manual_mapping_curation]
    right_mappings = [m for m in right_mappings if m.justification == manual_mapping_curation]

    left_dd = defaultdict(list)
    right_dd = defaultdict(list)
    for mapping in left_mappings:
        left_dd[mapping.subject, mapping.object].append(mapping)
    for _k, values in left_dd.items():
        if len(values) > 1:
            pass
    left_d = {so: values[0] for so, values in left_dd.items() if len(values) == 1}

    for mapping in right_mappings:
        right_dd[mapping.subject, mapping.object].append(mapping)
    for _k, values in right_dd.items():
        if len(values) > 1:
            pass
    right_d = {so: values[0] for so, values in right_dd.items() if len(values) == 1}

    # TODO check when entity in left set is mapped to different entity in right set

    left_only = set(left_d) - set(right_d)
    right_only = set(right_d) - set(left_d)
    both = set(right_d).intersection(left_d)

    rv = "## Comparison\n\n"
    rv += f"- {len(left_only)} subject-object pairs {left_label} only\n"
    rv += f"- {len(right_only)} subject-object pairs {right_label} only\n"
    rv += f"- {len(both)} subject-object pairs both\n"

    rv += "\n\n"
    if venn_type == "svg":
        rv += get_matplotlib_venn2(
            left=len(left_only),
            right=len(right_only),
            both=len(both),
            left_label=left_label,
            right_label=right_label,
        )
    elif venn_type == "mermaid":
        rv += get_mermaid_venn2_markdown(
            left=len(left_only),
            right=len(right_only),
            both=len(both),
            left_label=left_label,
            right_label=right_label,
        )
    else:
        raise ValueError(f"Unknown venn_type: {venn_type}")
    rv += "\n\n"

    rows = []

    for k in both:
        left = left_d[k]
        right = right_d[k]
        if left.predicate != right.predicate:
            rows.append(
                (
                    k[0].curie,
                    k[0].name,
                    k[1].curie,
                    k[1].name,
                    "different predicate",
                    left.predicate.curie,
                    right.predicate.curie,
                )
            )
        elif left.predicate_modifier != right.predicate_modifier:
            rows.append(
                (
                    k[0].curie,
                    k[0].name,
                    k[1].curie,
                    k[1].name,
                    "different predicate modifier",
                    left.predicate_modifier or "",
                    right.predicate_modifier or "",
                )
            )

    if both:
        rv += "\n\n## Differences\n\n"
        rv += (
            tabulate(
                rows,
                headers=[
                    "subject_id",
                    "subject_label",
                    "object_id",
                    "object_label",
                    "warning",
                    left_label,
                    right_label,
                ],
                tablefmt="github",
            )
            + "\n"
        )
    return rv


def get_mermaid_venn2_markdown(
    left: int, right: int, both: int, left_label: str | None = None, right_label: str | None = None
) -> str:
    """Get a mermaid venn diagram."""
    return dedent(f"""\
    ```mermaid
    {get_mermaid_venn2(left, right, both, left_label=left_label, right_label=right_label)}
    ```
    """)


def get_mermaid_venn2(
    left: int, right: int, both: int, left_label: str | None = None, right_label: str | None = None
) -> str:
    """Get a mermaid venn diagram."""
    if left_label is None:
        left_label = "left"
    if right_label is None:
        right_label = "right"
    return dedent(f"""\
        venn-beta
          set A["{left_label}"]:{left}
          set B["{right_label}"]:{right}
          union A,B["Overlap"]:{both}
    """)


def get_matplotlib_venn2(
    left: int, right: int, both: int, left_label: str | None = None, right_label: str | None = None
) -> str:
    """Get SVG from matplotlib."""
    import matplotlib.pyplot as plt
    from matplotlib_venn import venn2

    fig = plt.figure(figsize=(4, 2.5))
    venn2(
        subsets=(left, right, both),
        set_labels=(left_label, right_label),
    )
    return fig_to_markdown_svg(fig)


def fig_to_markdown_svg(fig: matplotlib.figure.Figure) -> str:
    """Convert a matplotlib figure to an embedded SVG markdown string."""
    buf = io.StringIO()
    fig.savefig(buf, format="svg", bbox_inches="tight")
    svg_string = buf.getvalue()
    buf.close()
    # Raw SVG can be dropped directly into Markdown (e.g., in HTML-capable renderers)
    return svg_string


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


@click.command()
@click.argument("left_url")
@click.argument("right_url")
@click.option("--left-label")
@click.option("--right-label")
@click.option("--output", type=Path)
def _demo(
    left_url: str,
    right_url: str,
    left_label: str | None,
    right_label: str | None,
    output: Path | None,
) -> None:
    import sys

    import pystow.utils

    module = pystow.module("tmp")

    target_prefix = "FIX"
    internal_cache_path = module.join(name=f"{target_prefix}-rsc.sssom.tsv")
    internal_mappings, internal_title = _do_it(left_url, internal_cache_path, target_prefix)
    external_cache_path = module.join(name=f"{target_prefix}-wg-onto.sssom.tsv")
    external_mappings, external_title = _do_it(right_url, external_cache_path, target_prefix)

    markdown = compare(
        internal_mappings,
        external_mappings,
        left_label or internal_title or "left",
        right_label or external_title or "right",
    )
    pystow.utils.safe_write_text(markdown, output or sys.stdout)


if __name__ == "__main__":
    _demo()
