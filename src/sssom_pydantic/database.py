"""Database model."""

from __future__ import annotations

import datetime
from typing import Any, ClassVar, Literal

from curies import Reference
from curies.database import (
    get_reference_list_sa_column,
    get_reference_sa_column,
)
from pydantic import AnyUrl
from sqlalchemy import Dialect, TypeDecorator
from sqlalchemy.sql.type_api import TypeEngine
from sqlmodel import JSON, Column, Field, SQLModel, String
from typing_extensions import Self

from sssom_pydantic import MappingTool, SemanticMapping
from sssom_pydantic.models import Cardinality

__all__ = [
    "SemanticMappingModel",
]


class MappingToolTypeDecorator(TypeDecorator[MappingTool]):
    """A SQLAlchemy type decorator for a mapping tool."""

    impl: ClassVar[type[TypeEngine[str]]] = JSON  # type:ignore[misc]
    #: Set SQLAlchemy caching to true
    cache_ok: ClassVar[bool] = True  # type:ignore[misc]

    def process_bind_param(
        self, value: MappingTool | None, dialect: Dialect
    ) -> dict[str, Any] | None:
        """Convert the Python object into a database value."""
        if value is None:
            return None
        return value.model_dump()

    def process_result_value(
        self, value: dict[str, Any] | None, dialect: Dialect
    ) -> MappingTool | None:
        """Convert the database value into a Python object."""
        if value is None:
            return None
        return MappingTool.model_validate(value)


class AnyURLTypeDecorator(TypeDecorator[AnyUrl]):
    """A SQLAlchemy type decorator for a URL."""

    impl: ClassVar[type[TypeEngine[str]]] = String  # type:ignore[misc]
    #: Set SQLAlchemy caching to true
    cache_ok: ClassVar[bool] = True  # type:ignore[misc]

    def process_bind_param(self, value: AnyUrl | None, dialect: Dialect) -> str | None:
        """Convert the Python object into a database value."""
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value: str | None, dialect: Dialect) -> AnyUrl | None:
        """Convert the database value into a Python object."""
        if value is None:
            return None
        return AnyUrl(value)


class SemanticMappingModel(SQLModel, table=True):
    """A model."""

    id: int | None = Field(default=None, primary_key=True)

    # required
    subject: Reference = Field(sa_column=get_reference_sa_column())
    predicate: Reference = Field(sa_column=get_reference_sa_column())
    object: Reference = Field(sa_column=get_reference_sa_column())
    justification: Reference = Field(..., sa_column=get_reference_sa_column())
    predicate_modifier: Literal["Not"] | None = Field(None, sa_type=String)

    # core
    record: Reference | None = Field(None, sa_column=get_reference_sa_column())
    authors: list[Reference] | None = Field(None, sa_column=get_reference_list_sa_column())
    confidence: float | None = Field(None)
    mapping_tool: MappingTool | None = Field(None, sa_column=Column(MappingToolTypeDecorator()))
    license: str | None = Field(None)

    # rest
    subject_category: str | None = Field(None)
    subject_match_field: list[Reference] | None = Field(
        None, sa_column=get_reference_list_sa_column()
    )
    subject_preprocessing: list[Reference] | None = Field(
        None, sa_column=get_reference_list_sa_column()
    )
    subject_source: Reference | None = Field(None, sa_column=get_reference_sa_column())
    subject_source_version: str | None = Field(None)
    subject_type: str | None = Field(None)

    predicate_type: Reference | None = Field(None, sa_column=get_reference_sa_column())

    object_category: str | None = Field(None)
    object_match_field: list[Reference] | None = Field(
        None, sa_column=get_reference_list_sa_column()
    )
    object_preprocessing: list[Reference] | None = Field(
        None, sa_column=get_reference_list_sa_column()
    )
    object_source: Reference | None = Field(None, sa_column=get_reference_sa_column())
    object_source_version: str | None = Field(None)
    object_type: str | None = Field(None)

    creators: list[Reference] | None = Field(None, sa_column=get_reference_list_sa_column())
    reviewers: list[Reference] | None = Field(None, sa_column=get_reference_list_sa_column())

    publication_date: datetime.date | None = Field(None)
    mapping_date: datetime.date | None = Field(None)

    comment: str | None = Field(None)
    curation_rule: list[Reference] | None = Field(None, sa_column=get_reference_list_sa_column())
    curation_rule_text: list[str] | None = Field(None, sa_type=JSON)
    issue_tracker_item: Reference | None = Field(None, sa_column=get_reference_sa_column())

    #: see https://mapping-commons.github.io/sssom/MappingCardinalityEnum/
    #: and https://w3id.org/sssom/mapping_cardinality
    cardinality: Cardinality | None = Field(None, sa_type=String)
    cardinality_scope: list[str] | None = Field(None, sa_type=JSON)
    # https://w3id.org/sssom/mapping_provider
    provider: AnyUrl | None = Field(None, sa_column=Column(AnyURLTypeDecorator()))
    # https://w3id.org/sssom/mapping_source
    source: Reference | None = Field(None, sa_column=get_reference_sa_column())

    match_string: list[str] | None = Field(None, sa_type=JSON)

    other: dict[str, str] | None = Field(None, sa_type=JSON)
    see_also: list[str] | None = Field(None, sa_type=JSON)
    similarity_measure: str | None = Field(None)
    similarity_score: float | None = Field(None)

    @classmethod
    def from_semantic_mapping(cls, mapping: SemanticMapping) -> Self:
        """Get from a non-ORM mapping."""
        return cls.model_validate(mapping.model_dump())

    def to_semantic_mapping(self) -> SemanticMapping:
        """Get a non-ORM mapping."""
        return SemanticMapping.model_validate(self.model_dump())
