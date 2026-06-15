"""Compare semantic mappings.

.. code-block:: console

    $ sssom_pydantic subset -i https://github.com/nfdi-de/section-metadata-wg-onto/raw/refs/heads/main/sssom/data/positive.sssom.tsv \
        --prefix CHMO \
        --target-prefix FIX \
        --standardize \
        --output nfdi-chmo-fix.sssom.tsv
    $ sssom_pydantic compare \
        https://github.com/NFDI4Chem/rsc-cmo/raw/refs/heads/Add-tsv-files/src/mappings/fix-mappings.sssom.tsv \
        nfdi-chmo-fix.sssom.tsv \
        --left-label Ambika \
        --right-label Charlie
"""  # noqa:E501

import io
from collections import defaultdict
from collections.abc import Collection, Iterable
from textwrap import dedent
from typing import TYPE_CHECKING, Any, Generic, Literal, NamedTuple, TypeAlias, TypeVar

from curies import NamableReference
from curies.vocabulary import manual_mapping_curation
from tabulate import tabulate
from typing_extensions import Self

from sssom_pydantic import SemanticMapping

if TYPE_CHECKING:
    import matplotlib.figure

__all__ = ["get_comparison_markdown"]

X = TypeVar("X")
Y = TypeVar("Y")
NestedIndex: TypeAlias = defaultdict[X, defaultdict[X, list[Y]]]
PairIndex: TypeAlias = defaultdict[tuple[X, X], list[Y]]

SUBJECT_OBJECT_CELL_HEADER = ["subject_id", "subject_label", "object_id", "object_label"]


def _subject_object_cells(
    k: tuple[NamableReference, NamableReference],
) -> tuple[str, str, str, str]:
    return k[0].curie, k[0].name or "", k[1].curie, k[1].name or ""


def get_comparison_markdown(
    left_mappings: Iterable[SemanticMapping],
    right_mappings: Iterable[SemanticMapping],
    left_label: str,
    right_label: str,
    venn_type: Literal["svg", "mermaid"] | None = None,
) -> str:
    """Compare two sets of mappings and get Markdown.

    :param left_mappings: left mappings
    :param right_mappings: right mappings
    :param left_label: The label for the left mapping source
    :param right_label: The label for the right mapping source
    :param venn_type: The mechanism for producing a venn diagram

    .. warning:: This function assumes that the mappings are only from a
        one prefix to another prefix
    """
    left_mappings_ = [m for m in left_mappings if m.justification == manual_mapping_curation]
    right_mappings_ = [m for m in right_mappings if m.justification == manual_mapping_curation]

    left_subject_prefixes = {m.subject.prefix for m in left_mappings_}
    left_object_prefixes = {m.object.prefix for m in left_mappings_}
    right_subject_prefixes = {m.subject.prefix for m in right_mappings_}
    right_object_prefixes = {m.object.prefix for m in right_mappings_}
    if len(left_subject_prefixes) != 1:
        raise ValueError
    if len(left_object_prefixes) != 1:
        raise ValueError
    if left_subject_prefixes != right_subject_prefixes:
        raise ValueError
    if left_object_prefixes != right_object_prefixes:
        raise ValueError

    rv = ""

    left_subject_index: NestedIndex[NamableReference, SemanticMapping] = defaultdict(
        lambda: defaultdict(list)
    )
    right_subject_index: NestedIndex[NamableReference, SemanticMapping] = defaultdict(
        lambda: defaultdict(list)
    )
    left_object_index: NestedIndex[NamableReference, SemanticMapping] = defaultdict(
        lambda: defaultdict(list)
    )
    right_object_index: NestedIndex[NamableReference, SemanticMapping] = defaultdict(
        lambda: defaultdict(list)
    )
    left_dd: PairIndex[NamableReference, SemanticMapping] = defaultdict(list)
    right_dd: PairIndex[NamableReference, SemanticMapping] = defaultdict(list)

    for mapping in left_mappings_:
        left_subject_index[mapping.subject][mapping.object].append(mapping)
        left_object_index[mapping.object][mapping.subject].append(mapping)
        left_dd[mapping.subject, mapping.object].append(mapping)
    for mapping in right_mappings_:
        right_subject_index[mapping.subject][mapping.object].append(mapping)
        right_object_index[mapping.object][mapping.subject].append(mapping)
        right_dd[mapping.subject, mapping.object].append(mapping)

    duplicates = []
    for k, values in left_dd.items():
        if len(values) > 1:
            duplicates.append((left_label, *_subject_object_cells(k)))
    for k, values in right_dd.items():
        if len(values) > 1:
            duplicates.append((right_label, *_subject_object_cells(k)))

    if duplicates:
        rv += "\n\n## Duplicates\n\n"
        rv += tabulate(duplicates, headers=["side", *SUBJECT_OBJECT_CELL_HEADER], tablefmt="github")
        rv += "\n\n"

    left_d = {so: values[0] for so, values in left_dd.items() if len(values) == 1}
    right_d = {so: values[0] for so, values in right_dd.items() if len(values) == 1}

    def _yyyy(x: set[NamableReference]) -> str:
        return ", ".join(sorted(f"{a.curie} ({a.name})" for a in x))

    subject_rows = []
    # TODO check when entity in left set is mapped to different entity in right set
    for subject, (l_only, b_both, r_only) in _get_nested_index_venns(
        left_subject_index, right_subject_index
    ):
        if l_only or r_only:
            subject_rows.append(
                (subject.curie, subject.name, _yyyy(l_only), _yyyy(b_both), _yyyy(r_only))
            )
    if subject_rows:
        subject_venn = VennSets.from_collections(left_subject_index, right_subject_index)
        rv += "\n\n## Subject Comparison\n\n"
        rv += f"- {len(subject_venn.left)} subjects in {left_label} only\n"
        rv += f"- {len(subject_venn.right)} subject in {right_label} only\n"
        rv += f"- {len(subject_venn.both)} subjects in both\n\n"
        rv += tabulate(
            subject_rows,
            headers=["subject_id", "subject_label", left_label, "both", right_label],
            tablefmt="github",
        )
        rv += "\n\n"

    object_rows = []
    for obj, (l_only, b_both, r_only) in _get_nested_index_venns(
        left_object_index, right_object_index
    ):
        if l_only or r_only:
            object_rows.append((obj.curie, obj.name, _yyyy(l_only), _yyyy(b_both), _yyyy(r_only)))
    if object_rows:
        object_venn = VennSets.from_collections(left_object_index, right_object_index)
        rv += "\n\n## Object Comparison\n\n"
        rv += f"- {len(object_venn.left)} objects in {left_label} only\n"
        rv += f"- {len(object_venn.right)} objects in {right_label} only\n"
        rv += f"- {len(object_venn.both)} objects in both\n\n"
        rv += tabulate(
            object_rows,
            headers=["object_id", "object_label", left_label, "both", right_label],
            tablefmt="github",
        )
        rv += "\n\n"

    venn = VennSets.from_collections(left_d, right_d)

    rv += "\n\n## Subject-Object Pair Comparison\n\n"
    rv += f"- {len(venn.left)} subject-object pairs {left_label} only\n"
    rv += f"- {len(venn.right)} subject-object pairs {right_label} only\n"
    rv += f"- {len(venn.both)} subject-object pairs both\n"

    if venn_type is None:
        pass
    elif venn_type == "svg":
        rv += "\n\n"
        rv += get_matplotlib_venn2(venn, left_label=left_label, right_label=right_label)
        rv += "\n\n"
    elif venn_type == "mermaid":
        rv += "\n\n"
        rv += get_mermaid_venn2_markdown(venn, left_label=left_label, right_label=right_label)
        rv += "\n\n"

    subject_object_rows = []

    for k in venn.both:
        left = left_d[k]
        right = right_d[k]
        if left.predicate != right.predicate:
            msg = "different predicate"
            subject_object_rows.append(
                (*_subject_object_cells(k), msg, left.predicate.curie, right.predicate.curie)
            )
        elif left.predicate_modifier != right.predicate_modifier:
            msg = "different predicate modifier"
            subject_object_rows.append(
                (
                    *_subject_object_cells(k),
                    msg,
                    left.predicate_modifier or "",
                    right.predicate_modifier or "",
                )
            )

    if subject_object_rows:
        rv += "\n\n"
        rv += (
            tabulate(
                subject_object_rows,
                headers=[*SUBJECT_OBJECT_CELL_HEADER, "warning", left_label, right_label],
                tablefmt="github",
            )
            + "\n"
        )
    return rv


class VennCounts(NamedTuple):
    """A representation of the counts in a venn diagram."""

    left: int
    both: int
    right: int


V = TypeVar("V", default=Any)


class VennSets(NamedTuple, Generic[V]):
    """Represents the elements unique to a left and right set, and their shared elements."""

    left: set[V]
    both: set[V]
    right: set[V]

    @classmethod
    def from_collections(cls, left: Collection[V], right: Collection[V]) -> Self:
        """Construct from two collections."""
        left = set(left)
        right = set(right)
        return cls(left - right, left & right, right - left)

    def get_counts(self) -> VennCounts:
        """Get counts."""
        return VennCounts(len(self.left), len(self.both), len(self.right))


def _get_nested_index_venns(
    left: NestedIndex[X, Any], right: NestedIndex[X, Any]
) -> Iterable[tuple[X, VennSets[X]]]:
    for element in set(right).intersection(left):
        yield element, VennSets.from_collections(left[element], right[element])


def get_mermaid_venn2_markdown(
    venn: VennCounts | VennSets, left_label: str | None = None, right_label: str | None = None
) -> str:
    """Get a mermaid venn diagram."""
    rv = "```mermaid\n"
    rv += get_mermaid_venn2(venn, left_label=left_label, right_label=right_label)
    rv += "```"
    return rv


def get_mermaid_venn2(
    venn: VennSets | VennCounts,
    *,
    left_label: str | None = None,
    right_label: str | None = None,
) -> str:
    """Get a mermaid venn diagram."""
    if left_label is None:
        left_label = "left"
    if right_label is None:
        right_label = "right"
    if isinstance(venn, VennSets):
        venn = venn.get_counts()
    return dedent(f"""\
        venn-beta
          set A["{left_label}"]:{venn.left}
          set B["{right_label}"]:{venn.right}
          union A,B["Overlap"]:{venn.both}
    """)


def get_matplotlib_venn2(
    venn: VennSets | VennCounts,
    *,
    left_label: str | None = None,
    right_label: str | None = None,
) -> str:
    """Get SVG from matplotlib."""
    import matplotlib.pyplot as plt
    from matplotlib_venn import venn2

    if isinstance(venn, VennCounts):
        subsets = venn.left, venn.right, venn.both
    else:
        subsets = len(venn.left), len(venn.right), len(venn.both)

    fig = plt.figure(figsize=(4, 2.5))
    venn2(subsets=subsets, set_labels=(left_label, right_label))
    return fig_to_markdown_svg(fig)


def fig_to_markdown_svg(fig: matplotlib.figure.Figure) -> str:
    """Convert a matplotlib figure to an embedded SVG markdown string."""
    buf = io.StringIO()
    fig.savefig(buf, format="svg", bbox_inches="tight")
    svg_string = buf.getvalue()
    buf.close()
    # Raw SVG can be dropped directly into Markdown (e.g., in HTML-capable renderers)
    return svg_string
