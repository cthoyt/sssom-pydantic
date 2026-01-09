"""Example mappings, (eventually) covering the entirety of the SSSOM spec."""

from __future__ import annotations

import datetime

from curies import NamableReference, NamedReference, Reference
from curies.vocabulary import (
    charlie,
    lexical_matching_process,
    manual_mapping_curation,
    semantic_similarity,
)
from pydantic import BaseModel

from sssom_pydantic import SemanticMapping
from sssom_pydantic.api import MappingTool, mapping_hash_v1

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


# the simplest possible mapping
simple = SemanticMapping(
    subject=R1,
    predicate=P1,
    object=R2,
    justification=manual_mapping_curation.curie,
)

e1_with_hash = ExampleMapping(
    description="A simple mapping with a reference for the mapping itself in the `record` field",
    semantic_mapping=simple.model_copy(update={"record": mapping_hash_v1(simple)}),
)

simple_with_author = ExampleMapping(
    description="A simple mapping with an author",
    semantic_mapping=simple.model_copy(update={"authors": [charlie]}),
)
simple_with_reviewer = ExampleMapping(
    description="A simple mapping with a reviewer",
    semantic_mapping=simple.model_copy(update={"reviewers": [charlie]}),
)
simple_with_creator = ExampleMapping(
    description="A simple mapping with a creator",
    semantic_mapping=simple.model_copy(update={"creators": [charlie]}),
)
simple_with_confidence = ExampleMapping(
    description="A simple mapping with a confidence",
    semantic_mapping=simple.model_copy(update={"confidence": 0.99}),
)
simple_with_comment = ExampleMapping(
    description="A simple mapping with a comment",
    semantic_mapping=simple.model_copy(update={"comment": "a great mapping"}),
)
simple_with_license = ExampleMapping(
    description="A simple mapping with a license",
    semantic_mapping=simple.model_copy(update={"license": "https://spdx.org/licenses/CC-BY-4.0"}),
)
simple_with_modifier = ExampleMapping(
    description="A simple mapping with a license",
    semantic_mapping=simple.model_copy(update={"predicate_modifier": "Not"}),
)
simple_with_categories = ExampleMapping(
    description="A simple mapping with subject and object categories",
    semantic_mapping=simple.model_copy(
        update={
            "subject_category": "biolink:Chemical",
            "object_category": "biolink:Chemical",
        }
    ),
)

simple_predicted = SemanticMapping(
    subject=R1,
    predicate=P1,
    object=R2,
    justification=lexical_matching_process.curie,
)

simple_with_match_field = ExampleMapping(
    description="A simple mapping with subject and object match fields",
    semantic_mapping=simple_predicted.model_copy(
        update={
            "subject_match_field": "rdfs:label",
            "object_match_field": "rdfs:label",
        }
    ),
)
simple_with_preprocessing = ExampleMapping(
    description="A simple mapping with subject and object preprocessing",
    semantic_mapping=simple_predicted.model_copy(
        update={
            "subject_preprocessing": "semapv:Stemming",
            "object_preprocessing": "semapv:Stemming",
        }
    ),
)
simple_with_mapping_tool = ExampleMapping(
    description="A simple mapping with a mapping tool",
    semantic_mapping=simple_predicted.model_copy(
        update={
            "mapping_tool": MappingTool(name="test tool"),
        }
    ),
)

simple_with_similarity = ExampleMapping(
    description="A simple mapping with a similarity measure and score",
    semantic_mapping=SemanticMapping(
        subject=R1,
        predicate=P1,
        object=R2,
        justification=semantic_similarity.curie,
        similarity_measure="wikidata:Q865360",
        similarity_score=0.75,
    ),
)

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
