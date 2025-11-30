"""Example mappings, (eventually) covering the entirety of the SSSOM spec."""

from __future__ import annotations

import datetime

from curies import NamableReference, NamedReference, Reference
from curies.vocabulary import manual_mapping_curation

from sssom_pydantic import SemanticMapping

__all__ = [
    "EXAMPLE_MAPPINGS",
]

R1 = NamedReference(prefix="mesh", identifier="C000089", name="ammeline")
R2 = NamedReference(prefix="chebi", identifier="28646", name="ammeline")
P1 = NamableReference(prefix="skos", identifier="exactMatch")

EXAMPLE_MAPPINGS = [
    SemanticMapping(
        subject=R1,
        predicate=P1,
        object=R2,
        source=Reference.from_curie("w3id:biopragmatics/biomappings/sssom/biomappings.sssom.tsv"),
        justification=manual_mapping_curation.curie,
    ),
    SemanticMapping(  # test multiple random keys in `other`
        subject=R1,
        predicate=P1,
        object=R2,
        justification=manual_mapping_curation.curie,
        other={"key1": "value1", "key2": "value2"},
    ),
    SemanticMapping(  # test a single key in `other`
        subject=R1,
        predicate=P1,
        object=R2,
        justification=manual_mapping_curation.curie,
        other={"key": "value"},
    ),
    SemanticMapping(
        subject=R1,
        predicate=P1,
        object=R2,
        justification=manual_mapping_curation.curie,
        cardinality="1:1",
    ),
    SemanticMapping(
        subject=R1,
        predicate=P1,
        object=R2,
        justification=manual_mapping_curation.curie,
        provider="https://github.com/biopragmatics/biomappings",
    ),
    SemanticMapping(
        subject=R1,
        subject_type=Reference.from_curie("owl:Class"),
        predicate=P1,
        object=R2,
        object_type=Reference.from_curie("owl:Class"),
        justification=manual_mapping_curation.curie,
        provider="https://github.com/biopragmatics/biomappings",
    ),
    # This example is about when the mapping was done
    SemanticMapping(
        subject=R1,
        predicate=P1,
        object=R2,
        justification=manual_mapping_curation.curie,
        mapping_date=datetime.date(2025, 11, 30),
    ),
    # This example is about when the mapping was done + publication
    SemanticMapping(
        subject=R1,
        predicate=P1,
        object=R2,
        justification=manual_mapping_curation.curie,
        mapping_date=datetime.date(2025, 11, 29),
        publication_date=datetime.date(2025, 11, 30),
    ),
]
