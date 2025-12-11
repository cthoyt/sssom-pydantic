"""This is a placeholder for putting the main code for your module."""

from __future__ import annotations

import datetime
import functools
import hashlib
import warnings
from collections.abc import Callable
from typing import Any, Literal, TypeAlias

import curies
from curies import NamableReference, Reference, Triple
from curies.mixins import SemanticallyStandardizable
from curies.vocabulary import matching_processes
from pydantic import AnyUrl, BaseModel, ConfigDict, Field
from typing_extensions import Self

from .constants import MULTIVALUED, PROPAGATABLE, Row
from .models import Cardinality, Record

__all__ = [
    "NOT",
    "CoreSemanticMapping",
    "ExtensionDefinition",
    "ExtensionDefinitionRecord",
    "MappingSet",
    "MappingSetRecord",
    "MappingTool",
    "PredicateModifier",
    "RequiredSemanticMapping",
    "SemanticMapping",
    "SemanticMappingHash",
    "SemanticMappingPredicate",
    "mapping_hash_v1",
]

PredicateModifier: TypeAlias = Literal["Not"]
NOT: PredicateModifier = "Not"


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
    predicate_modifier: PredicateModifier | None = Field(None)

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


class SemanticMapping(CoreSemanticMapping, SemanticallyStandardizable):
    """Represents all fields for SSSOM.."""

    model_config = ConfigDict(frozen=True)

    subject_category: str | None = Field(None)
    subject_match_field: list[Reference] | None = Field(None)
    subject_preprocessing: list[Reference] | None = Field(None)
    subject_source: Reference | None = Field(None)
    subject_source_version: str | None = Field(None)
    # https://w3id.org/sssom/subject_type
    subject_type: Reference | None = Field(None)

    predicate_type: Reference | None = Field(None)

    object_category: str | None = Field(None)
    object_match_field: list[Reference] | None = Field(None)
    object_preprocessing: list[Reference] | None = Field(None)
    object_source: Reference | None = Field(None)
    object_source_version: str | None = Field(None)
    object_type: Reference | None = Field(None)

    creators: list[Reference] | None = Field(
        None,
        description="The creator is the person responsible for the creation of the mapping. For"
        "example, if the mapping was produced by a lexical matching workflow, then the creator "
        "is the person who decided to run the workflow. This is _not_ the same as the person who "
        "developed the workflow. The creator is the one who takes responsibility for the creation "
        "of the mapping (but necessarily was the one who made it). If a person curates a de novo "
        "mapping directly, then they are both the creator and the author.",
    )
    # TODO maybe creator_labels
    reviewers: list[Reference] | None = Field(
        None,
        description="The reviewer is the person who looks at a mapping that has already been "
        "manually curated (i.e., has an author) and gives a second look. If the mapping was "
        "machine generated, then the person who takes a first look is not the reviewer, but "
        "actually the author.",
    )
    # TODO maybe reviewer_labels

    publication_date: datetime.date | None = Field(None)
    mapping_date: datetime.date | None = Field(None)

    comment: str | None = Field(None)
    curation_rule: list[Reference] | None = Field(None)
    curation_rule_text: list[str] | None = Field(None)
    issue_tracker_item: Reference | None = Field(None)

    #: see https://mapping-commons.github.io/sssom/MappingCardinalityEnum/
    #: and https://w3id.org/sssom/mapping_cardinality
    cardinality: Cardinality | None = Field(None)
    cardinality_scope: list[str] | None = Field(None)
    # https://w3id.org/sssom/mapping_provider
    provider: AnyUrl | None = Field(None)
    # https://w3id.org/sssom/mapping_source
    source: Reference | None = Field(None)

    match_string: list[str] | None = Field(None)

    other: dict[str, str] | None = Field(None)
    see_also: list[str] | None = Field(None)
    similarity_measure: str | None = Field(None)
    similarity_score: float | None = Field(None)

    def get_prefixes(self) -> set[str]:
        """Get prefixes used in this mapping."""
        rv = super().get_prefixes()
        for x in [
            self.subject_source,
            self.subject_type,
            self.predicate_type,
            self.object_source,
            self.object_type,
            self.source,
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
            subject_type=self.subject_type.curie if self.subject_type is not None else None,
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
            object_type=self.object_type.curie if self.object_type is not None else None,
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
            mapping_cardinality=self.cardinality,
            cardinality_scope=self.cardinality_scope,
            mapping_provider=str(self.provider) if self.provider else None,
            mapping_source=self.source.curie if self.source else None,
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
            other=_dict_to_other(self.other) if self.other else None,
            see_also=self.see_also,
            similarity_measure=self.similarity_measure,
            similarity_score=self.similarity_score,
        )

    def standardize(self, converter: curies.Converter) -> Self:
        """Standardize."""
        update: dict[str, Reference | list[Reference]] = {}
        for name, field_info in self.__class__.model_fields.items():
            value = getattr(self, name)
            if value is None:
                continue
            if field_info.annotation in {Reference, Reference | None}:
                update[name] = converter.standardize_reference(value, strict=True)
            elif field_info.annotation in {list[Reference], list[Reference] | None}:
                update[name] = [converter.standardize_reference(r, strict=True) for r in value]
        return self.model_copy(update=update)


OTHER_PRIMARY_SEP = "|"
OTHER_SECONDARY_SEP = "="


def _dict_to_other(x: dict[str, str]) -> str:
    return OTHER_PRIMARY_SEP.join(f"{k}{OTHER_SECONDARY_SEP}{v}" for k, v in sorted(x.items()))


def _other_to_dict(x: str) -> dict[str, str]:
    return dict(_xx(y) for y in x.split(OTHER_PRIMARY_SEP))


def _xx(s: str) -> tuple[str, str]:
    left, right = s.split(OTHER_SECONDARY_SEP)
    return left, right


#: A predicate for a semantic mapping
SemanticMappingPredicate: TypeAlias = Callable[[SemanticMapping], bool]

#: A function that hashes a semantic mapping into a reference
SemanticMappingHash: TypeAlias = Callable[[SemanticMapping], Reference]


class MappingTool(BaseModel):
    """Represents metadata about a mapping tool."""

    model_config = ConfigDict(frozen=True)

    reference: Reference | None = None
    name: str | None = None
    version: str | None = Field(None)


class MappingSetRecord(BaseModel):
    """Represents a mapping set, readily serializable for usage in SSSOM TSV."""

    model_config = ConfigDict(frozen=True)

    curie_map: dict[str, str] | None = None

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
    # note that this diverges from the SSSOM spec, which says license is required
    # and injects a placeholder license... I don't think this is actually valuable
    license: str | None = Field(None)
    issue_tracker: str | None = Field(None)
    extension_definitions: list[ExtensionDefinitionRecord] | None = Field(None)
    creator_id: list[str] | None = None
    creator_label: list[str] | None = None

    # propagatable slots
    cardinality_scope: list[str] | None = None
    curation_rule: list[str] | None = None
    curation_rule_text: list[str] | None = None
    mapping_date: datetime.date | None = None
    mapping_provider: str | None = None
    mapping_tool: str | None = None
    mapping_tool_id: str | None = None
    mapping_tool_version: str | None = None
    object_match_field: list[str] | None = None
    object_preprocessing: list[str] | None = None
    object_source: str | None = None
    object_source_version: str | None = None
    object_type: str | None = None
    predicate_type: str | None = None
    similarity_measure: str | None = None
    subject_match_field: list[str] | None = None
    subject_preprocessing: list[str] | None = None
    subject_source: str | None = None
    subject_source_version: str | None = None
    subject_type: str | None = None

    def process(self, converter: curies.Converter) -> MappingSet:
        """Get a mapping set."""
        return MappingSet(
            id=self.mapping_set_id,
            confidence=self.mapping_set_confidence,
            description=self.mapping_set_description,
            source=self.mapping_set_source,
            title=self.mapping_set_title,
            version=self.mapping_set_version,
            #
            publication_date=self.publication_date,
            see_also=self.see_also,
            other=_other_to_dict(self.other) if self.other else None,
            comment=self.comment,
            sssom_version=self.sssom_version,
            license=self.license,
            issue_tracker=self.issue_tracker,
            extension_definitions=list(self.extension_definitions)
            if self.extension_definitions
            else None,
            creators=[converter.parse_curie(c, strict=True) for c in self.creator_id]
            if self.creator_id
            else None,
            creator_label=self.creator_label,
        )

    def get_parser(self) -> Callable[[dict[str, str | list[str]]], Record]:
        """Get a row parser function."""
        propagatable = {}
        for key in PROPAGATABLE:
            prop_value = getattr(self, key)
            if not prop_value:
                continue
            # the following conditional fixes common mistakes in
            # encoding a multivalued slot with a single value
            if key in MULTIVALUED and isinstance(prop_value, str):
                prop_value = [prop_value]
            propagatable[key] = prop_value

        return functools.partial(row_to_record, propagatable=propagatable)


def row_to_record(row: Row, *, propagatable: dict[str, str | list[str]] | None = None) -> Record:
    """Parse a row from a SSSOM TSV file, unprocessed."""
    # Step 1: propagate values from the header if it's not explicit in the record
    if propagatable:
        row.update(propagatable)

    # Step 2: split all lists on the default SSSOM delimiter (pipe)
    for key in MULTIVALUED:
        if (value := row.get(key)) and isinstance(value, str):
            row[key] = [
                stripped_subvalue
                for subvalue in value.split("|")
                if (stripped_subvalue := subvalue.strip())
            ]

    rv = Record.model_validate(row)
    return rv


class MappingSet(BaseModel):
    """A processed representation of a mapping set."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(...)
    confidence: float | None = Field(None)
    description: str | None = Field(None)
    source: list[str] | None = Field(None)
    title: str | None = Field(None)
    version: str | None = Field(None)

    publication_date: datetime.date | None = Field(None)
    see_also: list[str] | None = Field(None)
    other: str | None = Field(None)
    comment: str | None = Field(None)
    sssom_version: str | None = Field(None)
    license: str | None = Field(None)
    issue_tracker: str | None = Field(None)
    extension_definitions: list[ExtensionDefinition] | None = Field(None)
    creators: list[Reference] | None = None
    creator_label: list[str] | None = None

    def to_record(self) -> MappingSetRecord:
        """Create a record, for dumping to SSSOM directly."""
        return MappingSetRecord(
            mapping_set_id=self.id,
            mapping_set_confidence=self.confidence,
            mapping_set_description=self.description,
            mapping_set_source=self.source,
            mapping_set_title=self.title,
            mapping_set_version=self.version,
            publication_date=self.publication_date,
            see_also=self.see_also,
            other=self.other,
            comment=self.comment,
            sssom_version=self.sssom_version,
            license=self.license,
            issue_tracker=self.issue_tracker,
            extension_definitions=[e.to_record() for e in self.extension_definitions]
            if self.extension_definitions
            else None,
            creator_id=[r.curie for r in self.creators] if self.creators else None,
            creator_label=self.creator_label,
        )

    def get_prefixes(self) -> set[str]:
        """Get prefixes appearing in all parts of the metadata."""
        rv: set[str] = set()
        for extension_definition in self.extension_definitions or []:
            rv.update(extension_definition.get_prefixes())
        for creator in self.creators or []:
            rv.add(creator.prefix)
        return rv


class ExtensionDefinitionRecord(BaseModel):
    """An extension definition that can be readily dumped to SSSOM."""

    slot_name: str
    property: str | None = None
    type_hint: str | None = None

    def process(self, converter: curies.Converter) -> ExtensionDefinition:
        """Process the SSSOM data structure into a more idiomatic one."""
        return ExtensionDefinition(
            slot_name=self.slot_name,
            property=converter.parse(self.property, strict=True).to_pydantic()
            if self.property
            else None,
            type_hint=converter.parse(self.type_hint, strict=True).to_pydantic()
            if self.type_hint
            else None,
        )


class ExtensionDefinition(BaseModel):
    """A processed extension definition."""

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

    def to_record(self) -> ExtensionDefinitionRecord:
        """Create a record object that can be readily dumped to SSSOM."""
        return ExtensionDefinitionRecord(
            slot_name=self.slot_name,
            property=self.property.curie if self.property else None,
            type_hint=self.type_hint.curie if self.type_hint else None,
        )


MAPPING_HASH_V1_PREFIX = "sssom-pydantic-mapping-hash-v2"
MAPPING_HASH_V1_EXCLUDE: set[str] = {"record", "cardinality", "cardinality_scope"}


def mapping_hash_v1(m: SemanticMapping) -> Reference:
    """Hash a mapping into a reference."""
    h = hashlib.md5(usedforsecurity=False)
    h.update(m.model_dump_json(exclude=MAPPING_HASH_V1_EXCLUDE).encode("utf8"))
    return Reference(prefix=MAPPING_HASH_V1_PREFIX, identifier=h.hexdigest())
