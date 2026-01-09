"""Example mappings, (eventually) covering the entirety of the SSSOM spec."""

from __future__ import annotations

import datetime

from curies import NamableReference, NamedReference, Reference
from curies.vocabulary import manual_mapping_curation
from pydantic import BaseModel

from sssom_pydantic import SemanticMapping

__all__ = [
    "EXAMPLES",
    "EXAMPLE_MAPPINGS",
]

R1 = NamedReference(prefix="mesh", identifier="C000089", name="ammeline")
R2 = NamedReference(prefix="chebi", identifier="28646", name="ammeline")
P1 = NamableReference(prefix="skos", identifier="exactMatch")


class ExampleMapping(BaseModel):
    """A mapping plus an explanation."""

    description: str
    semantic_mapping: SemanticMapping


e1 = ExampleMapping(
    description="A simple mapping with a source",
    semantic_mapping=SemanticMapping(
        subject=R1,
        predicate=P1,
        object=R2,
        source=Reference.from_curie("w3id:biopragmatics/biomappings/sssom/biomappings.sssom.tsv"),
        justification=manual_mapping_curation.curie,
    ),
)

e2 = ExampleMapping(
    description="test multiple random keys in `other`",
    semantic_mapping=SemanticMapping(
        subject=R1,
        predicate=P1,
        object=R2,
        justification=manual_mapping_curation.curie,
        other={"key1": "value1", "key2": "value2"},
    ),
)

e3 = ExampleMapping(
    description="test a single key in `other`",
    semantic_mapping=SemanticMapping(
        subject=R1,
        predicate=P1,
        object=R2,
        justification=manual_mapping_curation.curie,
        other={"key": "value"},
    ),
)

e4 = ExampleMapping(
    description="test a mapping annotated with 1-1 cardinality",
    semantic_mapping=SemanticMapping(
        subject=R1,
        predicate=P1,
        object=R2,
        justification=manual_mapping_curation.curie,
        cardinality="1:1",
    ),
)
e4b = ExampleMapping(
    description="test a mapping annotated with 1-n cardinality",
    semantic_mapping=SemanticMapping(
        subject=R1,
        predicate=P1,
        object=R2,
        justification=manual_mapping_curation.curie,
        cardinality="1:n",
    ),
)
e4c = ExampleMapping(
    description="test a mapping annotated with n-1 cardinality",
    semantic_mapping=SemanticMapping(
        subject=R1,
        predicate=P1,
        object=R2,
        justification=manual_mapping_curation.curie,
        cardinality="n:1",
    ),
)
e4d = ExampleMapping(
    description="test a mapping annotated with n-n cardinality",
    semantic_mapping=SemanticMapping(
        subject=R1,
        predicate=P1,
        object=R2,
        justification=manual_mapping_curation.curie,
        cardinality="n:n",
    ),
)

e5 = ExampleMapping(
    description="test a mapping with a given provider as a URI",
    semantic_mapping=SemanticMapping(
        subject=R1,
        predicate=P1,
        object=R2,
        justification=manual_mapping_curation.curie,
        provider="https://github.com/biopragmatics/biomappings",
    ),
)

e6 = ExampleMapping(
    description="test a mapping that annotates explicit subject and object types",
    semantic_mapping=SemanticMapping(
        subject=R1,
        subject_type=Reference.from_curie("owl:Class"),
        predicate=P1,
        object=R2,
        object_type=Reference.from_curie("owl:Class"),
        justification=manual_mapping_curation.curie,
    ),
)

e7 = ExampleMapping(
    description="This example is about when the mapping was done",
    semantic_mapping=SemanticMapping(
        subject=R1,
        predicate=P1,
        object=R2,
        justification=manual_mapping_curation.curie,
        mapping_date=datetime.date(2025, 11, 30),
    ),
)

e8 = ExampleMapping(
    description="This example is about when the mapping was done + publication",
    semantic_mapping=SemanticMapping(
        subject=R1,
        predicate=P1,
        object=R2,
        justification=manual_mapping_curation.curie,
        mapping_date=datetime.date(2025, 11, 29),
        publication_date=datetime.date(2025, 11, 30),
    ),
)

EXAMPLES: list[ExampleMapping] = [v for v in locals().values() if isinstance(v, ExampleMapping)]

EXAMPLE_MAPPINGS: list[SemanticMapping] = [e.semantic_mapping for e in EXAMPLES]
