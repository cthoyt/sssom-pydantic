"""Test constants."""

from __future__ import annotations

from typing import Any

import curies
from curies import NamedReference, Reference
from curies.vocabulary import exact_match, manual_mapping_curation

from sssom_pydantic.api import SemanticMapping
from sssom_pydantic.constants import MAPPING_SET_ID_KEY, PREFIX_MAP_KEY
from sssom_pydantic.models import Record

__all__ = [
    "P1",
    "R1",
    "R2",
    "TEST_CONVERTER",
    "TEST_MAPPING_SET_ID",
    "TEST_METADATA_W_PREFIX_MAP",
    "TEST_PREFIX_MAP",
    "_m",
    "_r",
]

R1 = NamedReference(prefix="mesh", identifier="C000089", name="ammeline")
R2 = NamedReference(prefix="chebi", identifier="28646", name="ammeline")
P1 = Reference(prefix="skos", identifier="exactMatch")


def _m(**kwargs: Any) -> SemanticMapping:
    """Construct a base semantic mapping."""
    return SemanticMapping(
        subject=R1,
        predicate=P1,
        object=R2,
        justification=manual_mapping_curation,
        **kwargs,
    )


def _r(**kwargs: Any) -> Record:
    """Construct a base record."""
    return Record(
        subject_id=R1.curie,
        subject_label=R1.name,
        predicate_id=exact_match.curie,
        object_id=R2.curie,
        object_label=R2.name,
        mapping_justification=manual_mapping_curation.curie,
        **kwargs,
    )


TEST_MAPPING_SET_ID = "https://example.org/sssom.mappingset/1.sssom.tsv"
TEST_PREFIX_MAP = {
    "mesh": "http://id.nlm.nih.gov/mesh/",
    "chebi": "http://purl.obolibrary.org/obo/CHEBI_",
    # the following are the default ones
    "owl": "http://www.w3.org/2002/07/owl#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "semapv": "https://w3id.org/semapv/vocab/",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "sssom": "https://w3id.org/sssom/",
}
TEST_CONVERTER = curies.Converter.from_prefix_map(TEST_PREFIX_MAP)
TEST_METADATA = {
    MAPPING_SET_ID_KEY: TEST_MAPPING_SET_ID,
}
TEST_METADATA_W_PREFIX_MAP = {
    PREFIX_MAP_KEY: TEST_PREFIX_MAP,
    MAPPING_SET_ID_KEY: TEST_MAPPING_SET_ID,
}
