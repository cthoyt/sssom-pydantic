"""This is a placeholder for putting the main code for your module."""

from __future__ import annotations

import datetime
import warnings
from collections.abc import Callable
from typing import Any, Literal, TypeAlias

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
    "SemanticMappingPredicate",
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

    @property
    def mapping_justification(self) -> Reference:
        """Get the mapping justification."""
        warnings.warn("use justification directly", DeprecationWarning, stacklevel=2)
        return self.justification

    @property
    def subject_name(self) -> str | None:
        """Get the subject label, if available."""
        return _get_name(self.subject)

    @property
    def predicate_name(self) -> str | None:
        """Get the predicate label, if available."""
        return _get_name(self.predicate)

    @property
    def object_name(self) -> str | None:
        """Get the object label, if available."""
        return _get_name(self.object)

    def to_record(self) -> Record:
        """Get a record."""
        return Record(
            subject_id=self.subject.curie,
            subject_label=self.subject_name,
            #
            predicate_id=self.predicate.curie,
            predicate_label=self.predicate_name,
            predicate_modifier=self.predicate_modifier,
            #
            object_id=self.object.curie,
            object_label=self.object_name,
            mapping_justification=self.justification.curie,
        )

    def get_prefixes(self) -> set[str]:
        """Get prefixes used in this mapping."""
        return {
            self.subject.prefix,
            self.predicate.prefix,
            self.object.prefix,
            self.justification.prefix,
        }


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

    @property
    def mapping_tool_name(self) -> str | None:
        """Get the mapping tool label, if available."""
        if self.mapping_tool is None:
            return None
        return self.mapping_tool.name

    def to_record(self) -> Record:
        """Get a record."""
        return Record(
            record_id=self.record.curie if self.record is not None else None,
            #
            subject_id=self.subject.curie,
            subject_label=self.subject_name,
            #
            predicate_id=self.predicate.curie,
            predicate_label=self.predicate_name,
            predicate_modifier=self.predicate_modifier,
            #
            object_id=self.object.curie,
            object_label=self.object_name,
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
        )

    def get_prefixes(self) -> set[str]:
        """Get prefixes used in this mapping."""
        rv = super().get_prefixes()
        if self.record is not None:
            rv.add(self.record.prefix)
        for a in self.authors or []:
            rv.add(a.prefix)
        if self.mapping_tool and self.mapping_tool.reference:
            rv.add(self.mapping_tool.reference.prefix)
        return rv

    @property
    def author(self) -> Reference | None:
        """Get the single author or raise a value error."""
        if self.authors is None:
            return None
        if len(self.authors) != 1:
            raise ValueError
        return self.authors[0]

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
            self.mapping_tool_name or "",
        )


def _join(references: list[Reference] | None) -> list[str] | None:
    if not references:
        return None
    return [r.curie for r in references]


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
    # TODO maybe creator_labels
    reviewers: list[Reference] | None = Field(None)
    # TODO maybe reviewer_labels

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

    match_string: list[str] | None = Field(None)

    other: str | None = Field(None)
    see_also: list[str] | None = Field(None)
    similarity_measure: str | None = Field(None)
    similarity_score: float | None = Field(None)

    def get_prefixes(self) -> set[str]:
        """Get prefixes used in this mapping."""
        rv = super().get_prefixes()
        for x in [
            self.subject_source,
            self.predicate_type,
            self.object_source,
            self.mapping_source,
        ]:
            if x is not None:
                rv.add(x.prefix)
        for y in [
            self.subject_match_field,
            self.subject_preprocessing,
            self.object_match_field,
            self.object_preprocessing,
            self.creators,
            self.reviewers,
            self.curation_rule,
        ]:
            if y is not None:
                for z in y:
                    rv.add(z.prefix)
        return rv

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
            subject_label=self.subject_name,
            subject_category=self.subject_category,
            subject_match_field=self.subject_match_field,
            subject_preprocessing=self.subject_preprocessing,
            subject_source=self.subject_source,
            subject_source_version=self.subject_source_version,
            subject_type=self.subject_type,
            #
            predicate_id=self.predicate.curie,
            predicate_label=self.predicate_name,
            predicate_modifier=self.predicate_modifier,
            predicate_type=self.predicate_type,
            #
            object_id=self.object.curie,
            object_label=self.object_name,
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
        )


#: A predicate for a semantic mapping
SemanticMappingPredicate: TypeAlias = Callable[[SemanticMapping], bool]


class MappingTool(BaseModel):
    """Represents metadata about a mapping tool."""

    model_config = ConfigDict(frozen=True)

    reference: Reference | None = None
    name: str | None = None
    version: str | None = Field(None)


class MappingSet(BaseModel):
    """Represents metadata about a mapping set."""

    model_config = ConfigDict(frozen=True)

    mapping_set_id: str = Field(...)
    mapping_set_confidence: float | None = Field(None)
    mapping_set_description: str | None = Field(None)
    mapping_set_source: list[str] | None = Field(None)
    mapping_set_title: str | None = Field(None)
    mapping_set_version: str | None = Field(None)

    publication_date: datetime.date | None = Field(None)
    see_also: list[str] | None = Field(None)
    other: str | None = Field(None)
    comment: str | None = Field(None)
    sssom_version: str | None = Field(None)
    license: str | None = Field(None)
    issue_tracker: str | None = Field(None)
    extension_definitions: list[ExtensionDefinition] | None = Field(None)
    creator_id: list[Reference] | None = None
    creator_label: list[str] | None = None

    def get_prefixes(self) -> set[str]:
        """Get prefixes appearing in all parts of the metadata."""
        rv: set[str] = set()
        for extension_definition in self.extension_definitions or []:
            rv.update(extension_definition.get_prefixes())
        for creator in self.creator_id or []:
            rv.add(creator.prefix)
        return rv


class ExtensionDefinition(BaseModel):
    """An extension definition."""

    slot_name: str
    property: Reference | None = None
    type_hint: Reference | None = None

    def get_prefixes(self) -> set[str]:
        """Get prefixes in the extension definition."""
        rv: set[str] = set()
        if self.property is not None:
            rv.add(self.property.prefix)
        if self.type_hint is not None:
            rv.add(self.type_hint.prefix)
        return rv
