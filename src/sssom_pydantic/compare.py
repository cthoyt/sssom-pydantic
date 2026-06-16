"""Compare semantic mappings.

You can subset towards the specific one you want:

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

You can do a multi-comparison:

.. code-block:: console

    $ sssom_pydantic merge \
        --input https://github.com/NFDI4Chem/rsc-cmo/raw/refs/heads/Add-tsv-files/src/mappings/fix-mappings.sssom.tsv \
        --input https://github.com/NFDI4Chem/rsc-cmo/raw/refs/heads/Add-tsv-files/src/mappings/afo-mappings.sssom.tsv \
        --input https://github.com/NFDI4Chem/rsc-cmo/raw/refs/heads/Add-tsv-files/src/mappings/rex-mappings.sssom.tsv \
        --input https://github.com/NFDI4Chem/rsc-cmo/raw/refs/heads/Add-tsv-files/src/mappings/wikidata-mappings.sssom.tsv \
        --standardize \
        --output ambika.sssom.tsv
    $ sssom_pydantic compare \
        ambika.sssom.tsv \
        https://github.com/nfdi-de/section-metadata-wg-onto/raw/refs/heads/main/sssom/data/positive.sssom.tsv \
        --standardize \
        --left-label Ambika \
        --right-label Charlie

"""  # noqa:E501

from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping
from typing import Any, Generic, NamedTuple, TypeAlias, TypeVar

from curies import NamableReference
from curies.triples.model import TripleType
from curies.vocabulary import manual_mapping_curation
from tabulate import tabulate
from typing_extensions import Self

from sssom_pydantic import SemanticMapping

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
    *,
    show_missing: bool = False,
) -> str:
    """Get prefix indexes."""
    ll = _strat(left_mappings)
    rr = _strat(right_mappings)
    markdown = f"# Comparison between {left_label} and {right_label}\n\n"
    pairs = set(ll).union(set(rr))
    for pair in pairs:
        ll_sub = ll.get(pair, [])
        rr_sub = rr.get(pair, [])
        if (not ll_sub or not rr_sub) and not show_missing:
            continue
        markdown += f"\n\n## {pair[0]} to {pair[1]}\n\n"
        markdown += _get_comparison_markdown(
            left_prefix=pair[0],
            right_prefix=pair[1],
            left_mappings=ll_sub,
            right_mappings=rr_sub,
            left_label=left_label,
            right_label=right_label,
        )
    return markdown


def _strat(triples: Iterable[TripleType]) -> Mapping[tuple[str, str], list[TripleType]]:
    rv: defaultdict[tuple[str, str], list[TripleType]] = defaultdict(list)
    for triple in triples:
        rv[triple.subject.prefix, triple.object.prefix].append(triple)
    return dict(rv)


def _get_comparison_markdown(
    left_prefix: str,
    right_prefix: str,
    left_mappings: Iterable[SemanticMapping],
    right_mappings: Iterable[SemanticMapping],
    left_label: str,
    right_label: str,
) -> str:
    """Compare two sets of mappings and get Markdown.

    :param left_mappings: left mappings
    :param right_mappings: right mappings
    :param left_label: The label for the left mapping source
    :param right_label: The label for the right mapping source

    .. warning:: This function assumes that the mappings are only from a
        one prefix to another prefix
    """
    left_mappings_ = [m for m in left_mappings if m.justification == manual_mapping_curation]
    right_mappings_ = [m for m in right_mappings if m.justification == manual_mapping_curation]

    if not left_mappings_ and not right_mappings_:
        return (
            f"No manually curated mappings from {left_prefix} to {right_prefix} "
            f"are available from either {left_label} or {right_label}"
        )
    elif not left_mappings_:
        return (
            f"No manually curated mappings from {left_prefix} to {right_prefix} "
            f"are available from {left_label}"
        )
    elif not right_mappings_:
        return (
            f"No manually curated mappings from {left_prefix} to {right_prefix} "
            f"are available from {right_label}"
        )

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
        rv += "\n\n### Duplicates\n\n"
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
        rv += "\n\n### Subject Comparison\n\n"
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
        rv += "\n\n### Object Comparison\n\n"
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

    rv += "\n\n### Subject-Object Pair Comparison\n\n"
    rv += f"- {len(venn.left)} subject-object pairs {left_label} only\n"
    rv += f"- {len(venn.right)} subject-object pairs {right_label} only\n"
    rv += f"- {len(venn.both)} subject-object pairs both\n"

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
