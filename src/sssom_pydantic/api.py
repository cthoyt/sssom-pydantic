"""This is a placeholder for putting the main code for your module."""

from __future__ import annotations

import datetime
import warnings
from typing import Any, Literal

from curies import NamableReference, Reference, Triple
from curies.vocabulary import matching_processes
from pydantic import BaseModel, ConfigDict, Field

from .models import Cardinality, Record

__all__ = [
    "CoreSemanticMapping",
    "MappingSet",
    "MappingTool",
    "RequiredSemanticMapping",
    "SemanticMapping",
    "sort_mappings",
]


class RequiredSemanticMapping(Triple):
    """Represents the required fields for SSSOM."""

    model_config = ConfigDict(frozen=True)

    justification: Reference = Field(
        ...,
        description="""\
        A `semapv <https://bioregistry.io/registry/semapv>`_ term describing
        the mapping type.

        These are relatively high level, and can be any child of ``semapv:Matching``,
        including:

        1. ``semapv:LexicalMatching``
        2. ``semapv:LogicalReasoning``
        """,
        examples=list(matching_processes),
    )
    predicate_modifier: Literal["Not"] | None = Field(None)
    mapping_set: MappingSet

    def to_record(self) -> Record:
        """Get a record."""
        return Record(
            subject_id=self.subject.curie,
            subject_label=_get_name(self.subject),
            #
            predicate_id=self.predicate.curie,
            predicate_label=_get_name(self.predicate),
            predicate_modifier=self.predicate_modifier,
            #
            object_id=self.object.curie,
            object_label=_get_name(self.object),
            mapping_justification=self.justification.curie,
            #
            mapping_set_id=self.mapping_set.id,
            mapping_set_confidence=self.mapping_set.confidence,
            mapping_set_description=self.mapping_set.description,
            mapping_set_source=self.mapping_set.source,
            mapping_set_title=self.mapping_set.title,
            mapping_set_version=self.mapping_set.version,
        )


def _get_name(reference: Reference) -> str | None:
    if isinstance(reference, NamableReference):
        return reference.name
    return None


class CoreSemanticMapping(RequiredSemanticMapping):
    """Represents the most useful fields for SSSOM."""

    model_config = ConfigDict(frozen=True)

    record: Reference | None = Field(None)
    authors: list[Reference] | None = Field(None)
    confidence: float | None = Field(None)
    mapping_tool: MappingTool | None = Field(None)
    license: str | None = Field(None)

    def to_record(self) -> Record:
        """Get a record."""
        return Record(
            record_id=self.record.curie if self.record is not None else None,
            #
            subject_id=self.subject.curie,
            subject_label=_get_name(self.subject),
            #
            predicate_id=self.predicate.curie,
            predicate_label=_get_name(self.predicate),
            predicate_modifier=self.predicate_modifier,
            #
            object_id=self.object.curie,
            object_label=_get_name(self.object),
            mapping_justification=self.justification.curie,
            #
            license=self.license,
            author_id=_join(self.authors),
            mapping_tool=self.mapping_tool.name
            if self.mapping_tool is not None and self.mapping_tool.name is not None
            else None,
            mapping_tool_id=self.mapping_tool.reference.curie
            if self.mapping_tool is not None and self.mapping_tool.reference is not None
            else None,
            mapping_tool_version=self.mapping_tool.version
            if self.mapping_tool is not None and self.mapping_tool.version is not None
            else None,
            confidence=self.confidence,
            #
            mapping_set_id=self.mapping_set.id,
            mapping_set_confidence=self.mapping_set.confidence,
            mapping_set_description=self.mapping_set.description,
            mapping_set_source=self.mapping_set.source,
            mapping_set_title=self.mapping_set.title,
            mapping_set_version=self.mapping_set.version,
        )

    @property
    def author(self) -> Reference | None:
        """Get the single author or raise a value error."""
        if self.authors is None:
            return None
        if len(self.authors) != 1:
            raise ValueError
        return self.authors[0]

    @property
    def mapping_justification(self) -> Reference | None:
        """Get the mapping justification."""
        warnings.warn("use justification directly", DeprecationWarning, stacklevel=2)
        return self.justification

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, CoreSemanticMapping):
            raise TypeError
        return self._key() < other._key()

    def _key(self) -> tuple[str, ...]:
        """Return a tuple for sorting mapping dictionaries."""
        return (
            self.subject.curie,
            self.predicate.curie,
            self.object.curie,
            self.justification.curie,
            self.mapping_tool.name
            if self.mapping_tool is not None and self.mapping_tool.name is not None
            else "",
        )


def _join(references: list[Reference] | None) -> str | None:
    if not references:
        return None
    return "|".join(r.curie for r in references)


class SemanticMapping(CoreSemanticMapping):
    """Represents all fields for SSSOM.."""

    model_config = ConfigDict(frozen=True)

    subject_category: str | None = Field(None)
    subject_match_field: list[Reference] | None = Field(None)
    subject_preprocessing: list[Reference] | None = Field(None)
    subject_source: Reference | None = Field(None)
    subject_source_version: str | None = Field(None)
    subject_type: str | None = Field(None)

    predicate_type: Reference | None = Field(None)

    object_category: str | None = Field(None)
    object_match_field: list[Reference] | None = Field(None)
    object_preprocessing: list[Reference] | None = Field(None)
    object_source: Reference | None = Field(None)
    object_source_version: str | None = Field(None)
    object_type: str | None = Field(None)

    creators: list[Reference] | None = Field(None)
    reviewers: list[Reference] | None = Field(None)

    publication_date: datetime.date | None = Field(None)
    mapping_date: datetime.date | None = Field(None)

    comment: str | None = Field(None)
    curation_rule: list[Reference] | None = Field(None)
    curation_rule_text: list[str] | None = Field(None)
    issue_tracker_item: Reference | None = Field(None)

    #: see https://mapping-commons.github.io/sssom/MappingCardinalityEnum/
    mapping_cardinality: Cardinality | None = Field(None)
    cardinality_scope: list[str] | None = Field(None)
    mapping_provider: str | None = Field(None)
    mapping_source: Reference | None = Field(None)

    match_string: str | None = Field(None)

    other: str | None = Field(None)
    see_also: str | None = Field(None)
    similarity_measure: str | None = Field(None)
    similarity_score: float | None = Field(None)

    def to_record(self) -> Record:
        """Get a record."""
        if self.mapping_tool is None:
            _mapping_tool, _mapping_tool_id, _mapping_tool_version = None, None, None
        else:
            pass

        return Record(
            record_id=self.record.curie if self.record is not None else None,
            #
            subject_id=self.subject.curie,
            subject_label=_get_name(self.subject),
            subject_category=self.subject_category,
            subject_match_field=self.subject_match_field,
            subject_preprocessing=self.subject_preprocessing,
            subject_source=self.subject_source,
            subject_source_version=self.subject_source_version,
            subject_type=self.subject_type,
            #
            predicate_id=self.predicate.curie,
            predicate_label=_get_name(self.predicate),
            predicate_modifier=self.predicate_modifier,
            predicate_type=self.predicate_type,
            #
            object_id=self.object.curie,
            object_label=_get_name(self.object),
            object_category=self.object_category,
            object_match_field=self.object_match_field,
            object_preprocessing=self.object_preprocessing,
            object_source=self.object_source,
            object_source_version=self.object_source_version,
            object_type=self.object_type,
            #
            mapping_justification=self.justification.curie,
            #
            author_id=_join(self.authors),
            author_label=None,  # FIXME
            creator_id=_join(self.creators),
            creator_label=None,  # FIXME
            reviewer_id=_join(self.reviewers),
            reviewer_label=None,  # FIXME
            #
            publication_date=self.publication_date,
            mapping_date=self.mapping_date,
            #
            comment=self.comment,
            confidence=self.confidence,
            curation_rule=self.curation_rule,
            curation_rule_text=self.curation_rule_text,
            issue_tracker_item=self.issue_tracker_item,
            license=self.license,
            #
            mapping_cardinality=self.mapping_cardinality,
            cardinality_scope=self.cardinality_scope,
            mapping_provider=self.mapping_provider,
            mapping_source=self.mapping_source,
            mapping_tool=self.mapping_tool.name
            if self.mapping_tool is not None and self.mapping_tool.name is not None
            else None,
            mapping_tool_id=self.mapping_tool.reference.curie
            if self.mapping_tool is not None and self.mapping_tool.reference is not None
            else None,
            mapping_tool_version=self.mapping_tool.version
            if self.mapping_tool is not None and self.mapping_tool.version is not None
            else None,
            match_string=self.match_string,
            #
            other=self.other,
            see_also=self.see_also,
            similarity_measure=self.similarity_measure,
            similarity_score=self.similarity_score,
            #
            mapping_set_id=self.mapping_set.id,
            mapping_set_confidence=self.mapping_set.confidence,
            mapping_set_description=self.mapping_set.description,
            mapping_set_source=self.mapping_set.source,
            mapping_set_title=self.mapping_set.title,
            mapping_set_version=self.mapping_set.version,
        )


class MappingTool(BaseModel):
    """Represents metadata about a mapping tool."""

    model_config = ConfigDict(frozen=True)

    reference: Reference | None = None
    name: str | None = None
    version: str | None = Field(None)


class MappingSet(BaseModel):
    """Represents metadata about a mapping set."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(...)

    confidence: float | None = Field(None)
    description: str | None = Field(None)
    source: str | None = Field(None)
    title: str | None = Field(None)
    version: str | None = Field(None)
