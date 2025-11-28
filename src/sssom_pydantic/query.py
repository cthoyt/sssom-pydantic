"""Tools for filtering mappings."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from .api import SemanticMapping

if TYPE_CHECKING:
    pass  # type:ignore[attr-defined]

__all__ = [
    "Query",
    "filter_mappings",
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


def filter_mappings(mappings: Iterator[SemanticMapping], state: Query) -> Iterator[SemanticMapping]:
    """Filter mappings based on a query."""
    for name, model_field in Query.model_fields.items():
        value = getattr(state, name)
        if not value:
            continue
        if model_field.annotation == str | None:
            value = value.casefold()
            get_strings = QUERY_TO_FUNC[name]
            mappings = (
                mapping
                for mapping in mappings
                if any(value in string.casefold() for string in get_strings(mapping) if string)
            )
        elif name == "same_text":
            mappings = (
                mapping
                for mapping in mappings
                if mapping.subject_name
                and mapping.object_name
                and mapping.subject_name.casefold() == mapping.object_name.casefold()
                and mapping.predicate.curie == "skos:exactMatch"
            )
        else:
            raise NotImplementedError
    yield from mappings


QUERY_TO_FUNC: dict[str, Callable[[SemanticMapping], list[str]]] = {
    "query": lambda mapping: [
        mapping.subject.curie,
        mapping.subject_name,
        mapping.object.curie,
        mapping.object_name,
        mapping.mapping_tool_name,
    ],
    "subject_prefix": lambda mapping: [mapping.subject.curie],
    "subject_query": lambda mapping: [mapping.subject.curie, mapping.subject_name],
    "object_query": lambda mapping: [mapping.object.curie, mapping.object_name],
    "object_prefix": lambda mapping: [mapping.object.curie],
    "prefix": lambda mapping: [mapping.subject.curie, mapping.object.curie],
    "mapping_tool": lambda mapping: [mapping.mapping_tool_name],
}
