"""Example mappings, (eventually) covering the entirety of the SSSOM spec."""

from __future__ import annotations

import datetime

from curies import Converter, NamableReference, NamedReference, Reference
from curies.vocabulary import (
    charlie,
    lexical_matching_process,
    manual_mapping_curation,
    semantic_similarity,
)
from pydantic import BaseModel

from sssom_pydantic.api import (
    MAPPING_HASH_V1_PREFIX,
    MAPPING_HASH_V1_URI_PREFIX,
    MappingTool,
    SemanticMapping,
    mapping_hash_v1,
)

__all__ = [
    "EXAMPLES",
    "EXAMPLE_MAPPINGS",
    "P1",
    "R1",
    "R2",
]
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
    #
    "spdx": "https://spdx.org/licenses/",
    "w3id": "https://w3id.org/",
    MAPPING_HASH_V1_PREFIX: MAPPING_HASH_V1_URI_PREFIX,
    "issue": "https://github.com/cthoyt/sssom-pydantic/issues/",
    "biolink": "https://w3id.org/biolink/vocab/",
    "rule": "https://example.org/disease-rule/",
    "bioregistry": "https://bioregistry.io/",
    "orcid": "https://orcid.org/",
}
TEST_CONVERTER = Converter.from_prefix_map(TEST_PREFIX_MAP)
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
    description="reference for the mapping itself in the `record` field",
    semantic_mapping=simple.model_copy(update={"record": mapping_hash_v1(simple, TEST_CONVERTER)}),
)

simple_with_author = ExampleMapping(
    description="author",
    semantic_mapping=simple.model_copy(update={"authors": [charlie]}),
)
simple_with_reviewer = ExampleMapping(
    description="reviewer",
    semantic_mapping=simple.model_copy(update={"reviewers": [charlie]}),
)
simple_with_reviewer_and_date = ExampleMapping(
    description="reviewer and date of review",
    semantic_mapping=simple.model_copy(
        update={"reviewers": [charlie], "review_date": datetime.date(2021, 1, 1)}
    ),
)
simple_with_reviewer_and_score = ExampleMapping(
    description="reviewer and confidence",
    semantic_mapping=simple.model_copy(update={"reviewers": [charlie], "reviewer_agreement": 0.99}),
)
simple_with_creator = ExampleMapping(
    description="creator",
    semantic_mapping=simple.model_copy(update={"creators": [charlie]}),
)
simple_with_confidence = ExampleMapping(
    description="confidence",
    semantic_mapping=simple.model_copy(update={"confidence": 0.99}),
)
simple_with_comment = ExampleMapping(
    description="comment",
    semantic_mapping=simple.model_copy(update={"comment": "a great mapping"}),
)
simple_with_license = ExampleMapping(
    description="license",
    semantic_mapping=simple.model_copy(update={"license": "https://spdx.org/licenses/CC-BY-4.0"}),
)
simple_with_modifier = ExampleMapping(
    description="predicate modifier",
    semantic_mapping=simple.model_copy(update={"predicate_modifier": "Not"}),
)
simple_with_categories = ExampleMapping(
    description="subject and object categories",
    semantic_mapping=simple.model_copy(
        update={
            "subject_category": Reference.from_curie("biolink:Chemical"),
            "object_category": Reference.from_curie("biolink:Chemical"),
        }
    ),
)
simple_with_issue_tracker = ExampleMapping(
    description="issue tracker",
    semantic_mapping=simple.model_copy(
        update={"issue_tracker_item": Reference.from_curie("issue:1")}
    ),
)
simple_with_see_also = ExampleMapping(
    description="see also list",
    semantic_mapping=simple.model_copy(
        update={
            "see_also": [
                "https://example.org/a",
                "https://example.org/b",
            ]
        }
    ),
)
simple_with_sources = ExampleMapping(
    description="subject and object sources",
    semantic_mapping=simple.model_copy(
        update={
            "subject_source": Reference.from_curie("bioregistry:mesh"),
            "subject_source_version": "2025",
            "object_source": Reference.from_curie("bioregistry:chebi"),
            "object_source_version": "150",
        }
    ),
)
simple_with_predicate_type = ExampleMapping(
    description="predicate type",
    semantic_mapping=simple.model_copy(
        update={
            "predicate_type": Reference.from_curie("owl:AnnotationProperty"),
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
    description="subject and object match fields",
    semantic_mapping=simple_predicted.model_copy(
        update={
            "subject_match_field": [Reference.from_curie("rdfs:label")],
            "object_match_field": [Reference.from_curie("rdfs:label")],
        }
    ),
)
simple_with_preprocessing = ExampleMapping(
    description="subject and object preprocessing",
    semantic_mapping=simple_predicted.model_copy(
        update={
            "subject_preprocessing": [Reference.from_curie("semapv:Stemming")],
            "object_preprocessing": [Reference.from_curie("semapv:Stemming")],
            "match_string": ["ammeline"],
        }
    ),
)
simple_with_mapping_tool = ExampleMapping(
    description="mapping tool",
    semantic_mapping=simple_predicted.model_copy(
        update={
            "mapping_tool": MappingTool(name="test tool"),
        }
    ),
)
simple_with_curation_rule = ExampleMapping(
    description="curation rule",
    semantic_mapping=simple_predicted.model_copy(
        update={
            "curation_rule": [Reference.from_curie("rule:MPR2")],
        }
    ),
)
simple_with_curation_rule_text = ExampleMapping(
    description="curation rule as text",
    semantic_mapping=simple_predicted.model_copy(
        update={
            "curation_rule_text": ["vibed it"],
        }
    ),
)


simple_with_similarity = ExampleMapping(
    description="similarity measure and score",
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
    description="source",
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
    description="1-1 cardinality",
    semantic_mapping=SemanticMapping(
        subject=R1,
        predicate=P1,
        object=R2,
        justification=manual_mapping_curation.curie,
        cardinality="1:1",
    ),
)
e4b = ExampleMapping(
    description="1-n cardinality",
    semantic_mapping=SemanticMapping(
        subject=R1,
        predicate=P1,
        object=R2,
        justification=manual_mapping_curation.curie,
        cardinality="1:n",
    ),
)
e4c = ExampleMapping(
    description="n-1 cardinality",
    semantic_mapping=SemanticMapping(
        subject=R1,
        predicate=P1,
        object=R2,
        justification=manual_mapping_curation.curie,
        cardinality="n:1",
    ),
)
e4d = ExampleMapping(
    description="n-n cardinality",
    semantic_mapping=SemanticMapping(
        subject=R1,
        predicate=P1,
        object=R2,
        justification=manual_mapping_curation.curie,
        cardinality="n:n",
    ),
)
e4d_scoped = ExampleMapping(
    description="n-n cardinality and cardinality scope",
    semantic_mapping=SemanticMapping(
        subject=R1,
        predicate=P1,
        object=R2,
        justification=manual_mapping_curation.curie,
        cardinality="n:n",
        cardinality_scope=["object_source", "predicate_id"],
    ),
)

e5 = ExampleMapping(
    description="provider as a URI",
    semantic_mapping=SemanticMapping(
        subject=R1,
        predicate=P1,
        object=R2,
        justification=manual_mapping_curation.curie,
        provider="https://github.com/biopragmatics/biomappings",
    ),
)

e6 = ExampleMapping(
    description="explicit subject and object types",
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
    description="mapping date",
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
