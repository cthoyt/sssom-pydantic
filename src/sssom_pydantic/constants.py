"""SSSOM constants."""

from __future__ import annotations

from typing import TypeAlias

import curies
from curies import Reference

__all__ = [
    "BUILTIN_CONVERTER",
    "DEFAULT_PREFIX_MAP",
    "MULTIVALUED",
    "PREDICATE_TYPES",
    "PREFIX_MAP_KEY",
    "PROPAGATABLE",
    "Row",
]

PREFIX_MAP_KEY = "curie_map"  # smh

#: Allowed predicate types
PREDICATE_TYPES: set[Reference] = {
    Reference(prefix="owl", identifier="Class"),
    Reference(prefix="owl", identifier="ObjectProperty"),
    Reference(prefix="owl", identifier="DataProperty"),
    Reference(prefix="owl", identifier="AnnotationProperty"),
    Reference(prefix="owl", identifier="NamedIndividual"),
    Reference(prefix="skos", identifier="Concept"),
    Reference(prefix="rdfs", identifier="Resource"),
    Reference(prefix="rdfs", identifier="Literal"),
    Reference(prefix="rdfs", identifier="Datatype"),
    Reference(prefix="rdf", identifier="Property"),
    Reference(prefix="sssom", identifier="ComposedEntityExpression"),
}

#: The set of values that should be propagated
#: from the frontmatter to all mappings
PROPAGATABLE: set[str] = {
    "cardinality_scope",
    "curation_rule",
    "curation_rule_text",
    "mapping_date",
    "mapping_provider",
    "mapping_tool",
    "mapping_tool_id",
    "mapping_tool_version",
    "object_match_field",
    "object_preprocessing",
    "object_source",
    "object_source_version",
    "object_type",
    "predicate_type",
    "similarity_measure",
    "subject_match_field",
    "subject_preprocessing",
    "subject_source",
    "subject_source_version",
    "subject_type",
}

#: An enumeration of the multivalued slots that are
#: applicable for mappings. Note, there's a unit
#: test that checks this is synced against the LinkML
#: schema
MULTIVALUED: set[str] = {
    "author_id",
    "author_label",  # reminder, this is independent from IDs
    "creator_id",
    "creator_label",  # reminder, this is independent from IDs
    "reviewer_id",
    "reviewer_label",  # reminder, this is independent from IDs
    "curation_rule",
    "curation_rule_text",
    "match_string",
    "see_also",
    "object_match_field",
    "object_preprocessing",
    "subject_match_field",
    "subject_preprocessing",
    "cardinality_scope",
}

#: The default prefix map for SSSOM
DEFAULT_PREFIX_MAP: dict[str, str] = {
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "orcid": "https://orcid.org/",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "sssom": "https://w3id.org/sssom/",
    "semapv": "https://w3id.org/semapv/vocab/",
    "owl": "http://www.w3.org/2002/07/owl#",
}
BUILTIN_CONVERTER = curies.Converter.from_prefix_map(DEFAULT_PREFIX_MAP)


MAPPING_SLOT_SPECIFIC = {
    "mapping_set_id",
    "mapping_set_confidence",
    "mapping_set_description",
    "mapping_set_source",
    "mapping_set_title",
    "mapping_set_version",
    #
    "sssom_version",
    "extension_definitions",
    "issue_tracker",
    "curie_map",
    # the following are not to be confused with mapping-level annotations
    "comment",
    "creator_id",
    "creator_label",
    "license",
    "publication_date",
    "other",
    "see_also",
}
MAPPING_SET_SLOTS_SKIP = {"mappings"}
MAPPING_SET_SLOTS = PROPAGATABLE | MAPPING_SLOT_SPECIFIC

Row: TypeAlias = dict[str, str | list[str]]
