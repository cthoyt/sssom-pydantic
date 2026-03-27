"""Tools for filtering mappings."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from typing import Any, Literal, NamedTuple, TypeAlias

from pydantic import BaseModel, Field

from .api import SemanticMapping

__all__ = [
    "Query",
    "Sort",
    "filter_mappings",
    "sort_mappings",
]


class Query(BaseModel):
    """A query over semantic mappings."""

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
    mappings: Iterable[SemanticMapping], query: Query | None
) -> Iterable[SemanticMapping]:
    """Filter mappings based on a query."""
    if query is None:
        yield from mappings
        return

    for name, model_field in Query.model_fields.items():
        value = getattr(query, name)
        if value is None:
            continue
        if model_field.annotation == str | None:
            mappings = _help_filter(mappings, name, value)
        elif name == "same_text":
            if value:
                mappings = (
                    mapping
                    for mapping in mappings
                    if mapping.subject_name
                    and mapping.object_name
                    and _str_norm(mapping.subject_name) == _str_norm(mapping.object_name)
                    and mapping.predicate.curie == "skos:exactMatch"
                )
            else:  # check that they're explicitly not the same
                mappings = (
                    mapping
                    for mapping in mappings
                    if mapping.predicate.curie == "skos:exactMatch"
                    and (
                        not mapping.subject_name
                        or not mapping.object_name
                        or _str_norm(mapping.subject_name) != _str_norm(mapping.object_name)
                    )
                )
        else:
            raise NotImplementedError
    yield from mappings


def _str_norm(s: str) -> str:
    return s.replace(" ", "").replace("-", "").lower()


def _help_filter(
    mappings: Iterable[SemanticMapping], name: str, value: str
) -> Iterable[SemanticMapping]:
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

#: Sort mechanisms
Sort: TypeAlias = Literal["asc", "desc", "subject", "object"]


class Sorter(NamedTuple):
    """A sorter."""

    key: Callable[[SemanticMapping], Any]
    reverse: bool

    def __call__(self, mappings: Iterable[SemanticMapping]) -> list[SemanticMapping]:
        """Sort the mappings."""
        return sorted(mappings, key=self.key, reverse=self.reverse)


def get_sorter(sort: str) -> Sorter:
    """Get a sort function."""
    if sort in {"desc", "confidence", "-confidence"}:
        return Sorter(key=lambda m: m.confidence or 0.0, reverse=True)
    elif sort in {"asc", "+confidence"}:
        return Sorter(key=lambda m: m.confidence or 0.0, reverse=False)
    elif sort == "+published":
        return Sorter(
            key=lambda m: (m.publication_date is not None, m.publication_date), reverse=False
        )
    elif sort in {"published", "-published"}:
        return Sorter(
            key=lambda m: (m.publication_date is not None, m.publication_date), reverse=True
        )
    elif sort == "subject":
        return Sorter(key=lambda m: m.subject.curie, reverse=False)
    elif sort == "object":
        return Sorter(lambda m: m.object.curie, reverse=False)
    else:
        raise ValueError


def sort_mappings(mappings: Iterator[SemanticMapping], sort: str) -> Iterator[SemanticMapping]:
    """Sort mappings."""
    sorter = get_sorter(sort)
    return iter(sorter(mappings))
