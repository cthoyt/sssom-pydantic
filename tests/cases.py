"""Test constants."""

from __future__ import annotations

from typing import Any

import curies
from curies import NamableReference, NamedReference, Reference
from curies.vocabulary import charlie, exact_match, manual_mapping_curation

from sssom_pydantic import MappingSetRecord
from sssom_pydantic.api import MAPPING_HASH_V1_PREFIX, SemanticMapping
from sssom_pydantic.models import Record

__all__ = [
    "P1",
    "R1",
    "R2",
    "TEST_CONVERTER",
    "TEST_MAPPING_SET",
    "TEST_MAPPING_SET_ID",
    "TEST_METADATA",
    "TEST_METADATA_W_PREFIX_MAP",
    "TEST_PREFIX_MAP",
    "_m",
    "_r",
]

R1 = NamedReference(prefix="mesh", identifier="C000089", name="ammeline")
R2 = NamedReference(prefix="chebi", identifier="28646", name="ammeline")
P1 = NamableReference(prefix="skos", identifier="exactMatch")
AUTHOR = charlie.pair.to_pydantic()


def _m(
    predicate: Reference | None = None, justification: Reference | None = None, **kwargs: Any
) -> SemanticMapping:
    """Construct a base semantic mapping."""
    return SemanticMapping(
        subject=R1,
        predicate=P1 if predicate is None else predicate,
        object=R2,
        justification=manual_mapping_curation.curie
        if justification is None
        else justification.curie,
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
    "spdx": "https://spdx.org/licenses/",
    "w3id": "https://w3id.org/",
    MAPPING_HASH_V1_PREFIX: f"https://w3id.org/sssom/{MAPPING_HASH_V1_PREFIX}/",
    "issue": "https://github.com/cthoyt/sssom-pydantic/issues/",
    "biolink": "https://w3id.org/biolink/vocab/",
    "rule": "https://example.org/disease-rule/",
    "bioregistry": "https://bioregistry.io/",
    "orcid": "https://orcid.org/",
}
TEST_CONVERTER = curies.Converter.from_prefix_map(TEST_PREFIX_MAP)
TEST_METADATA = MappingSetRecord(
    mapping_set_id=TEST_MAPPING_SET_ID,
    license="https://spdx.org/licenses/CC0-1.0",
)
TEST_MAPPING_SET = TEST_METADATA.process(TEST_CONVERTER)
TEST_METADATA_W_PREFIX_MAP = MappingSetRecord(
    curie_map=TEST_PREFIX_MAP,
    mapping_set_id=TEST_MAPPING_SET_ID,
    license="https://spdx.org/licenses/CC0-1.0",
)
