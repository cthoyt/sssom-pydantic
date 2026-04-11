"""Tools for filtering mappings."""

from __future__ import annotations

import typing
from collections import Counter
from collections.abc import Callable, Collection, Iterable, Sequence
from typing import TYPE_CHECKING, Any, Literal, NamedTuple, TypeAlias

from curies.triples import keep_references_either, keep_triples_by_hash
from pydantic import BaseModel, Field

from .api import SemanticMapping

if TYPE_CHECKING:
    from curies import Converter, NamableReference, Reference

__all__ = [
    "Query",
    "Sort",
    "count_entities",
    "count_prefix_pairs",
    "count_unique_entities",
    "filter_mappings",
    "get_mappings",
    "paginate_mappings",
    "sort_mappings",
]


class Query(BaseModel):
    """A query over semantic mappings."""

    triple_id: str | None = Field(
        None,
        description="The subject-predicate-object identifier, see https://curies.readthedocs.io/en/latest/api/curies.Converter.html#curies.Converter.hash_triple",
    )
    query: str | None = Field(
        None,
        description="If given, show only mappings that have it appearing as a substring "
        "in one of the source or target fields.",
    )
    subject_query: str | None = Field(
        None,
        description="If given, show only mappings that have it appearing as a substring "
        "in one of the source fields.",
    )
    subject_prefix: str | None = Field(
        None,
        description="If given, show only mappings that have it appearing in the "
        "source prefix field",
    )
    object_query: str | None = Field(
        None,
        description="If given, show only mappings that have it appearing as a substring "
        "in one of the target fields.",
    )
    object_prefix: str | None = Field(
        None,
        description="If given, show only mappings that have it appearing in the "
        "target prefix field",
    )
    mapping_tool: str | None = Field(
        None, description="If given, filters to mapping tool names matching this"
    )
    prefix: str | None = Field(
        None,
        description="If given, show only mappings that have it appearing as a "
        "substring in one of the prefixes.",
    )
    same_text: bool | None = Field(
        None, description="If true, filter to predictions with the same label"
    )


def filter_mappings(
    mappings: Iterable[SemanticMapping],
    query: Query | None,
    *,
    target_references: Collection[Reference] | None = None,
    converter: Converter | None = None,
) -> Iterable[SemanticMapping]:
    """Filter mappings based on a query."""
    if target_references is not None:
        mappings = keep_references_either(mappings, target_references)
    if query is not None:
        mappings = _query_helper(mappings, query, converter)
    yield from mappings


def _query_helper(
    mappings: Iterable[SemanticMapping], query: Query, converter: Converter | None
) -> Iterable[SemanticMapping]:
    for name, model_field in Query.model_fields.items():
        value = getattr(query, name)
        if value is None:
            continue
        if model_field.annotation == str | None:
            mappings = _help_filter(mappings, name, value, converter=converter)
        elif name == "same_text":
            mappings = _same_text(mappings, value)
        else:
            raise NotImplementedError
    return mappings


def _same_text(mappings: Iterable[SemanticMapping], value: bool) -> Iterable[SemanticMapping]:
    if value:
        return (
            mapping
            for mapping in mappings
            if mapping.subject_name
            and mapping.object_name
            and _str_norm(mapping.subject_name) == _str_norm(mapping.object_name)
            and mapping.predicate.curie == "skos:exactMatch"
        )
    else:  # check that they're explicitly not the same
        return (
            mapping
            for mapping in mappings
            if mapping.predicate.curie == "skos:exactMatch"
            and (
                not mapping.subject_name
                or not mapping.object_name
                or _str_norm(mapping.subject_name) != _str_norm(mapping.object_name)
            )
        )


def _str_norm(s: str) -> str:
    return s.replace(" ", "").replace("-", "").lower()


def _help_filter(
    mappings: Iterable[SemanticMapping],
    name: str,
    value: str,
    *,
    converter: Converter | None = None,
) -> Iterable[SemanticMapping]:
    if name == "triple_id":
        if converter is None:
            raise ValueError("filtering by identifier (i.e., mapping hash) requires a converter")
        yield from keep_triples_by_hash(mappings, converter, value)
    else:
        value = value.casefold()
        get_strings = QUERY_TO_FUNC[name]
        for mapping in mappings:
            if any(value in string.casefold() for string in get_strings(mapping) if string):
                yield mapping


#: A mapping from :class:`Query` fields to functions producing strings for checking
QUERY_TO_FUNC: dict[str, Callable[[SemanticMapping], list[str | None]]] = {
    "query": lambda mapping: [
        mapping.subject.curie,
        mapping.subject_name,
        mapping.object.curie,
        mapping.object_name,
        mapping.mapping_tool_name,
    ],
    "subject_prefix": lambda mapping: [mapping.subject.curie],
    "subject_query": lambda mapping: [mapping.subject.curie, mapping.subject_name],
    "object_prefix": lambda mapping: [mapping.object.curie],
    "object_query": lambda mapping: [mapping.object.curie, mapping.object_name],
    "prefix": lambda mapping: [mapping.subject.curie, mapping.object.curie],
    "mapping_tool": lambda mapping: [mapping.mapping_tool_name],
}


class Sorter(NamedTuple):
    """A sorter."""

    key: Callable[[SemanticMapping], Any]
    reverse: bool

    def __call__(self, mappings: Iterable[SemanticMapping]) -> list[SemanticMapping]:
        """Sort the mappings."""
        return sorted(mappings, key=self.key, reverse=self.reverse)


#: Sort mechanisms
Sort: TypeAlias = Literal[
    "asc",
    "desc",
    "confidence",
    "+confidence",
    "-confidence",
    "date",
    "+date",
    "-date",
    "date-published",
    "-date-published",
    "+date-published",
    "date-reviewed",
    "+date-reviewed",
    "-date-reviewed",
    "subject",
    "object",
]


def get_sorter(sort: Sort) -> Sorter:
    """Get a sort function."""
    match sort:
        case "desc" | "confidence" | "-confidence":
            return Sorter(key=lambda m: m.confidence or 0.0, reverse=True)
        case "asc" | "+confidence":
            return Sorter(key=lambda m: m.confidence or 0.0, reverse=False)
        case "date" | "-date":
            return Sorter(
                key=lambda m: (m.mapping_date is not None, m.publication_date), reverse=True
            )
        case "+date":
            return Sorter(
                key=lambda m: (m.mapping_date is not None, m.publication_date), reverse=False
            )
        case "date-published" | "-date-published":
            return Sorter(
                key=lambda m: (m.publication_date is not None, m.publication_date), reverse=True
            )
        case "date-reviewed" | "-date-reviewed":
            return Sorter(key=lambda m: (m.review_date is not None, m.review_date), reverse=True)
        case "+date-reviewed":
            return Sorter(key=lambda m: (m.review_date is not None, m.review_date), reverse=False)
        case "+date-published":
            return Sorter(
                key=lambda m: (m.publication_date is not None, m.publication_date), reverse=False
            )
        case "subject":
            return Sorter(key=lambda m: m.subject.curie, reverse=False)
        case "object":
            return Sorter(lambda m: m.object.curie, reverse=False)
        case _:
            if sort in typing.get_args(Sort):
                raise NotImplementedError(f"sort key not implemented: {sort}")
            raise ValueError(f"invalid sort value: {sort}")


def sort_mappings(mappings: Iterable[SemanticMapping], sort: Sort) -> list[SemanticMapping]:
    """Sort mappings."""
    sorter = get_sorter(sort)
    return sorter(mappings)


def get_mappings(
    mappings: Sequence[SemanticMapping],
    query: Query | None = None,
    *,
    limit: int | None = None,
    offset: int | None = None,
    order_by: Sort | None = None,
    converter: Converter | None = None,
) -> Sequence[SemanticMapping]:
    """Get a sequence of mappings."""
    if query is not None:
        mappings = list(filter_mappings(mappings, query, converter=converter))
    if order_by is not None:
        mappings = sort_mappings(mappings, order_by)
    if offset and offset < 0:
        raise ValueError("offset cannot be negative")
    if limit and limit < 0:
        raise ValueError("limit cannot be negative")
    if offset and limit:
        mappings = mappings[offset : offset + limit]
    elif offset:
        mappings = mappings[offset:]
    else:
        mappings = mappings[:limit]
    return mappings


def count_prefix_pairs(mappings: Iterable[SemanticMapping]) -> Counter[tuple[str, str]]:
    """Count subject/object prefix pairs."""
    return Counter((mapping.subject.prefix, mapping.object.prefix) for mapping in mappings)


def count_entities(mappings: Iterable[SemanticMapping]) -> Counter[Reference]:
    """Count appearances of subjects and objects."""
    return Counter(_subject_object_iterator(mappings))


def count_unique_entities(mappings: Iterable[SemanticMapping]) -> int:
    """Count the number of unique entities appearing in the subjects and objects of mappings."""
    return len(set(_subject_object_iterator(mappings)))


def _subject_object_iterator(mappings: Iterable[SemanticMapping]) -> Iterable[NamableReference]:
    for mapping in mappings:
        yield mapping.subject
        yield mapping.object


def paginate_mappings(
    mappings: Iterable[SemanticMapping],
    sort: Sort | None = None,
    offset: int | None = None,
    limit: int | None = None,
) -> Iterable[SemanticMapping]:
    """Paginate mappings with sort, offset, and limit operations."""
    it = iter(mappings)
    if sort is not None:
        it = iter(sort_mappings(it, sort))
    if offset is not None:
        try:
            for _ in range(offset):
                next(it)
        except StopIteration:
            # if next() fails, then there are no remaining entries.
            # do not pass go, do not collect 200 euro $
            return
    if limit is None:
        yield from it
    else:
        for line_prediction, _ in zip(it, range(limit), strict=False):
            yield line_prediction
