"""This is a placeholder for putting the main code for your module."""

from __future__ import annotations

import datetime
import functools
from collections.abc import Callable
from typing import Annotated, Any, Literal, TypeAlias

import curies
from curies import NamableReference, Reference, Triple
from curies.mixins import SemanticallyStandardizable
from curies.vocabulary import exact_match, matching_processes, unspecified_matching_process
from pydantic import AnyUrl, BaseModel, BeforeValidator, ConfigDict, Field
from typing_extensions import Self

from .constants import (
    ENTITY_TYPE_REFERENCE_TO_LITERAL,
    MULTIVALUED,
    PROPAGATABLE,
    EntityTypeLiteral,
    Row,
)
from .models import Cardinality, Record, expanded_record_to_str

__all__ = [
    "NOT",
    "ExtensionDefinition",
    "ExtensionDefinitionRecord",
    "MappingSet",
    "MappingSetRecord",
    "MappingTool",
    "PredicateModifier",
    "SemanticMapping",
    "SemanticMappingHash",
    "SemanticMappingPredicate",
    "hash_mapping",
    "hash_mapping_to_reference",
    "hash_triple",
]

PredicateModifier: TypeAlias = Literal["Not"]
NOT: PredicateModifier = "Not"


class MappingTool(BaseModel):
    """Represents metadata about a mapping tool."""

    model_config = ConfigDict(frozen=True)

    reference: Reference | None = None
    name: str | None = None
    version: str | None = Field(None)


def _ensure_namable(x: str | Reference | NamableReference) -> NamableReference:
    if isinstance(x, NamableReference):
        return x
    elif isinstance(x, Reference):
        return NamableReference.from_reference(x)
    elif isinstance(x, str):
        return NamableReference.from_curie(x)
    else:
        return x


def _get_name(reference: Reference) -> str | None:
    if isinstance(reference, NamableReference):
        return reference.name
    return None


def _join(references: list[Reference] | None) -> list[str] | None:
    if not references:
        return None
    return [r.curie for r in references]


FORWARDS_MAPS = {
    # get rid of the redundant suffix `_id`
    "record_id": "record",
    "subject_id": "subject",
    "predicate_id": "predicate",
    "object_id": "object",
    "reviewer_id": "reviewers",
    "author_id": "authors",
    "creator_id": "creators",
    # get rid of the redundant prefix `mapping_`
    "mapping_justification": "justification",
    "mapping_cardinality": "cardinality",
    "mapping_source": "source",
    "mapping_provider": "provider",
}

BACKWARDS_MAPS = {v: k for k, v in FORWARDS_MAPS.items()}


class SemanticMapping(Triple, SemanticallyStandardizable):
    """Represents most fields for SSSOM."""

    model_config = ConfigDict(frozen=True)

    subject: Annotated[NamableReference, BeforeValidator(_ensure_namable)] = Field(...)
    predicate: Annotated[NamableReference, BeforeValidator(_ensure_namable)] = Field(...)
    object: Annotated[NamableReference, BeforeValidator(_ensure_namable)] = Field(...)
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

    record: Reference | None = Field(None)
    authors: list[Reference] | None = Field(None)
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    mapping_tool: MappingTool | None = Field(None)
    license: str | None = Field(None)

    # https://w3id.org/sssom/subject_category
    subject_category: Reference | None = Field(None)
    subject_match_field: list[Reference] | None = Field(None)
    subject_preprocessing: list[Reference] | None = Field(None)
    subject_source: Reference | None = Field(None)
    subject_source_version: str | None = Field(None)
    # https://w3id.org/sssom/subject_type
    subject_type: Reference | None = Field(None)

    # TODO limit with https://mapping-commons.github.io/sssom/EntityTypeEnum/
    predicate_type: Reference | None = Field(None)

    object_category: Reference | None = Field(None)
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
    review_date: datetime.date | None = Field(None)
    reviewer_agreement: float | None = Field(None, ge=-1.0, le=1.0)

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
    similarity_score: float | None = Field(None, ge=0.0, le=1.0)

    @classmethod
    def from_triple(
        cls,
        subject: Reference,
        predicate: Reference,
        object: Reference,
        *,
        justification: Reference | None = None,
        **kwargs: Any,
    ) -> Self:
        """Construct a semantic mapping from a subject-predicate-object triple.

        :param subject: The subject of the mapping triple.
        :param predicate: The predicate of the mapping triple.
        :param object: The object of the mapping triple.
        :param justification: The justification of the mapping triple. Defaults to
            :data:`curies.vocabulary.unspecified_matching_process`
        :param kwargs: Additional fields to pass to the constructor

        :returns: A semantic mapping

        >>> from curies import Reference
        >>> from curies.vocabulary import exact_match
        >>> from sssom_pydantic import SemanticMapping
        >>> c1, c2, c3 = "DOID:0050577", "mesh:C562966", "umls:C4551571"
        >>> r1, r2, r3 = (Reference.from_curie(c) for c in (c1, c2, c3))
        >>> m1 = SemanticMapping.from_triple(r1, exact_match, r2)
        >>> m2 = SemanticMapping.from_triple(r2, exact_match, r3)
        >>> m3 = SemanticMapping.from_triple(r1, exact_match, r3)
        """
        return cls(
            subject=subject,
            predicate=predicate,
            object=object,
            justification=justification or unspecified_matching_process,
            **kwargs,
        )

    @classmethod
    def exact(
        cls,
        subject: Reference,
        object: Reference,
        *,
        justification: Reference | None = None,
        **kwargs: Any,
    ) -> Self:
        """Construct a ``skos:exactMatch`` mapping from a subject-object pair.

        :param subject: The subject of the mapping triple.
        :param object: The object of the mapping triple.
        :param justification: The justification of the mapping triple. Defaults to
            :data:`curies.vocabulary.unspecified_matching_process`
        :param kwargs: Additional fields to pass to the constructor

        :returns: A semantic mapping

        >>> from curies import Reference
        >>> from sssom_pydantic import SemanticMapping
        >>> c1, c2, c3 = "DOID:0050577", "mesh:C562966", "umls:C4551571"
        >>> r1, r2, r3 = (Reference.from_curie(c) for c in (c1, c2, c3))
        >>> m1 = SemanticMapping.exact(r1, r2)
        >>> m2 = SemanticMapping.exact(r2, r3)
        >>> m3 = SemanticMapping.exact(r1, r3)
        """
        return cls.from_triple(
            subject=subject,
            predicate=exact_match,
            object=object,
            justification=justification,
            **kwargs,
        )

    @property
    def negated(self) -> bool:
        """Check if the mapping record is negated."""
        return self.predicate_modifier == "Not"

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

    @property
    def mapping_tool_name(self) -> str | None:
        """Get the mapping tool label, if available."""
        if self.mapping_tool is None:
            return None
        return self.mapping_tool.name

    @property
    def author(self) -> Reference | None:
        """Get the single author or raise a value error."""
        if self.authors is None:
            return None
        if len(self.authors) != 1:
            raise ValueError
        return self.authors[0]

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, SemanticMapping):
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

    def get_prefixes(self) -> set[str]:
        """Get prefixes used in this mapping."""
        rv: set[str] = {
            self.subject.prefix,
            self.predicate.prefix,
            self.object.prefix,
            self.justification.prefix,
        }
        if self.record is not None:
            rv.add(self.record.prefix)
        for a in self.authors or []:
            rv.add(a.prefix)
        if self.mapping_tool and self.mapping_tool.reference:
            rv.add(self.mapping_tool.reference.prefix)
        for x in [
            self.subject_source,
            self.subject_type,
            self.predicate_type,
            self.object_source,
            self.object_type,
            self.source,
            self.issue_tracker_item,
            self.subject_category,
            self.object_category,
        ]:
            if x is not None:
                rv.add(x.prefix)
        for y in [
            self.subject_match_field,
            self.subject_preprocessing,
            self.object_match_field,
            self.object_preprocessing,
            self.authors,
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

        def _safe_curies(x: list[Reference] | None) -> list[str] | None:
            if not x:
                return None
            return [c.curie for c in x]

        def _safe_curie(x: Reference | None) -> str | None:
            if x is None:
                return None
            return x.curie

        def _safe_entity_type(x: Reference | None) -> EntityTypeLiteral | None:
            return ENTITY_TYPE_REFERENCE_TO_LITERAL[x] if x is not None else None

        return Record(
            record_id=_safe_curie(self.record),
            #
            subject_id=self.subject.curie,
            subject_label=self.subject_name,
            subject_category=_safe_curie(self.subject_category),
            subject_match_field=_safe_curies(self.subject_match_field),
            subject_preprocessing=_safe_curies(self.subject_preprocessing),
            subject_source=_safe_curie(self.subject_source),
            subject_source_version=self.subject_source_version,
            subject_type=_safe_entity_type(self.subject_type),
            #
            predicate_id=self.predicate.curie,
            predicate_label=self.predicate_name,
            predicate_modifier=self.predicate_modifier,
            predicate_type=_safe_entity_type(self.predicate_type),
            #
            object_id=self.object.curie,
            object_label=self.object_name,
            object_category=_safe_curie(self.object_category),
            object_match_field=_safe_curies(self.object_match_field),
            object_preprocessing=_safe_curies(self.object_preprocessing),
            object_source=_safe_curie(self.object_source),
            object_source_version=self.object_source_version,
            object_type=_safe_entity_type(self.object_type),
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
            review_date=self.review_date,
            reviewer_agreement=self.reviewer_agreement,
            #
            comment=self.comment,
            confidence=self.confidence,
            curation_rule=_safe_curies(self.curation_rule),
            curation_rule_text=self.curation_rule_text,
            issue_tracker_item=_safe_curie(self.issue_tracker_item),
            license=self.license,
            #
            mapping_cardinality=self.cardinality,
            cardinality_scope=self.cardinality_scope,
            mapping_provider=self.provider,
            mapping_source=_safe_curie(self.source),
            mapping_tool=self.mapping_tool.name
            if self.mapping_tool is not None and self.mapping_tool.name is not None
            else None,
            mapping_tool_id=_safe_curie(self.mapping_tool.reference)
            if self.mapping_tool is not None
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
            if field_info.annotation in {NamableReference, Reference, Reference | None}:
                update[name] = converter.standardize_reference(value, strict=True)
            elif field_info.annotation in {list[Reference], list[Reference] | None}:
                update[name] = [converter.standardize_reference(r, strict=True) for r in value]
        return self.model_copy(update=update)

    def negate(self) -> Self:
        """Return the negated version of this mapping."""
        if self.negated:
            return self.model_copy(update={"predicate_modifier": None})
        else:
            return self.model_copy(update={"predicate_modifier": NOT})


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
SemanticMappingHash: TypeAlias = Callable[[SemanticMapping, curies.Converter], Reference]


class MappingSetRecord(BaseModel):
    """Represents a mapping set, readily serializable for usage in SSSOM TSV."""

    model_config = ConfigDict(frozen=True)

    curie_map: dict[str, str] | None = None

    mapping_set_id: AnyUrl = Field(...)
    mapping_set_confidence: float | None = Field(None, ge=0.0, le=1.0)
    mapping_set_description: str | None = Field(None)
    mapping_set_source: list[AnyUrl] | None = Field(None)
    mapping_set_title: str | None = Field(None)
    mapping_set_version: str | None = Field(None)

    publication_date: datetime.date | None = Field(None)
    see_also: list[AnyUrl] | None = Field(None)
    other: str | None = Field(None)
    comment: str | None = Field(None)
    sssom_version: str | None = Field(None)
    # note that this diverges from the SSSOM spec, which says license is required
    # and injects a placeholder license... I don't think this is actually valuable
    license: AnyUrl | None = Field(None)
    issue_tracker: AnyUrl | None = Field(None)
    extension_definitions: list[ExtensionDefinitionRecord] | None = Field(None)
    creator_id: list[str] | None = None
    creator_label: list[str] | None = None

    # propagatable slots
    cardinality_scope: list[str] | None = None
    curation_rule: list[str] | None = None
    curation_rule_text: list[str] | None = None
    mapping_date: datetime.date | None = None
    mapping_provider: AnyUrl | None = None
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

    id: AnyUrl = Field(...)
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    description: str | None = Field(None)
    source: list[str] | None = Field(None)
    title: str | None = Field(None)
    version: str | None = Field(None)

    publication_date: datetime.date | None = Field(None)
    see_also: list[str] | None = Field(None)
    other: str | None = Field(None)
    comment: str | None = Field(None)
    sssom_version: str | None = Field(None)
    license: AnyUrl | None = Field(None)
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


MAPPING_HASH_CURIE_PREFIX = "sssom.record"
MAPPING_HASH_URI_PREFIX = "https://w3id.org/sssom/record/"


def hash_mapping_to_reference(mapping: SemanticMapping, converter: curies.Converter) -> Reference:
    """Hash a mapping into a reference."""
    identifier = hash_mapping(mapping, converter)
    return Reference(prefix=MAPPING_HASH_CURIE_PREFIX, identifier=identifier)


def hash_mapping(mapping: SemanticMapping, converter: curies.Converter) -> str:
    """Hash the entire SSSOM semantic mapping record.

    :param mapping: A semantic mapping
    :param converter: A converter

    :returns: A hexadecimal representation of the FNV64 hash of the canonical
        S-expression for the mapping, proposed in
        https://github.com/mapping-commons/sssom/pull/534.

    >>> from curies import NamedReference, Converter
    >>> from sssom_pydantic import SemanticMapping, hash_mapping
    >>> converter = Converter.from_prefix_map(
    ...     {
    ...         "CHEBI": "http://purl.obolibrary.org/obo/CHEBI_",
    ...         "mesh": "http://id.nlm.nih.gov/mesh/",
    ...         "skos": "http://www.w3.org/2004/02/skos/core#",
    ...         "semapv": "https://w3id.org/semapv/vocab/",
    ...     }
    ... )
    >>> mapping = SemanticMapping.exact(
    ...     subject=NamedReference(prefix="mesh", identifier="C000089", name="ammeline"),
    ...     object=NamedReference(prefix="CHEBI", identifier="28646", name="ammeline"),
    ... )
    >>> hash_mapping(mapping, converter)
    '9D59EF306286DC1A'

    .. note::

        This creates a hash over the entire SSSOM semantic mapping record. If you just
        want to hash the core triple (i.e., subject, predicate, predicate modifier, and
        object), then use :func:`hash_triple`
    """
    return _fnv64(mapping_to_sexpr_str(mapping, converter).encode("utf-8")).hex().upper()


FNV64_PRIME = 1099511628211
FNV64_OFFSET = 14695981039346656037
FNV64_MOD = 2**64


def _fnv64(data: bytes) -> bytes:
    h = FNV64_OFFSET
    for byte in data:
        h ^= byte
        h = (h * FNV64_PRIME) % FNV64_MOD
    return h.to_bytes(8, "little")


def mapping_to_sexpr_str(
    mapping: SemanticMapping, converter: curies.Converter, *, _debug: bool = False
) -> str:
    """Convert a mapping to a S-expression string."""
    expanded_record = mapping.to_record().expand(converter, exclude={"record_id"})
    return expanded_record_to_str(expanded_record, _debug=_debug)


def hash_triple(mapping: SemanticMapping, converter: curies.Converter) -> str:
    """Return a triples sameness identifier.

    :param mapping: A semantic mapping
    :param converter: A converter

    :returns: A mapping sameness identifier, which incorporates the subject, predicate,
        object, and predicate modifier based on
        https://ts4nfdi.github.io/mapping-sameness-identifier/

    >>> from sssom_pydantic import SemanticMapping, hash_triple
    >>> from curies import Converter
    >>> converter = Converter.from_prefix_map(
    ...     {
    ...         "CHEBI": "http://purl.obolibrary.org/obo/CHEBI_",
    ...         "mesh": "http://id.nlm.nih.gov/mesh/",
    ...         "skos": "http://www.w3.org/2004/02/skos/core#",
    ...         "semapv": "https://w3id.org/semapv/vocab/",
    ...     }
    ... )
    >>> mapping = SemanticMapping.exact("mesh:C000089", "CHEBI:28646")
    >>> hash_triple(mapping, converter)
    '36a1f9244ea7641a90987c82f33c25c0c13712ee8f48207b2a0825f8a4e4e26a'
    >>> hash_triple(mapping.negate(), converter)
    '36a1f9244ea7641a90987c82f33c25c0c13712ee8f48207b2a0825f8a4e4e26a~'
    """
    rv = converter.hash_triple(mapping)
    if mapping.negated:
        rv += "~"
    return rv
