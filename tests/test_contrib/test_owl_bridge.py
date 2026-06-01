"""Test bridge."""

import tempfile
import unittest
from pathlib import Path
from textwrap import dedent
from typing import Any

import functional_owl as f
from curies import NamableReference
from curies import vocabulary as v
from curies.vocabulary import charlie
from functional_owl import Axiom

from sssom_pydantic import NOT, SemanticMapping
from sssom_pydantic.contrib.owl_bridge import get_owl_bridge_axiom, write_owl_bridge
from tests.cases import TEST_CONVERTER, TEST_MAPPING_SET, _m

A = NamableReference.from_curie("a:1")
B = NamableReference.from_curie("b:1")


def _mapping(predicate: NamableReference, **kwargs: Any) -> SemanticMapping:
    return SemanticMapping(
        subject=A,
        predicate=predicate,
        object=B,
        justification=v.unspecified_matching_process,
        **kwargs,
    )


def _sc_mapping(
    child: NamableReference, parent: NamableReference, **kwargs: Any
) -> SemanticMapping:
    return SemanticMapping(
        subject=child,
        predicate=v.broad_match,
        object=parent,
        justification=v.unspecified_matching_process,
        **kwargs,
    )


cases: list[tuple[Axiom | None, SemanticMapping]] = [
    # exact match + no NOT
    (
        f.EquivalentClasses([A, B]),
        SemanticMapping.exact(A, B),
    ),
    (
        f.EquivalentClasses([A, B]),
        SemanticMapping.exact(A, B, subject_type=v.owl_class),
    ),
    (
        f.EquivalentObjectProperties([A, B]),
        SemanticMapping.exact(A, B, subject_type=v.owl_object_property),
    ),
    (
        f.EquivalentDataProperties([A, B]),
        SemanticMapping.exact(A, B, subject_type=v.owl_data_property),
    ),
    (
        f.SameIndividual([A, B]),
        SemanticMapping.exact(A, B, subject_type=v.owl_named_individual),
    ),
    (
        None,
        SemanticMapping.exact(A, B, subject_type=v.composed_entity_expression),
    ),
    # exact match + NOT
    (
        f.DisjointClasses([A, B]),
        SemanticMapping.exact(A, B, predicate_modifier=NOT),
    ),
    (
        f.DisjointClasses([A, B]),
        SemanticMapping.exact(A, B, subject_type=v.owl_class, predicate_modifier=NOT),
    ),
    (
        f.DisjointObjectProperties([A, B]),
        SemanticMapping.exact(A, B, subject_type=v.owl_object_property, predicate_modifier=NOT),
    ),
    (
        f.DisjointDataProperties([A, B]),
        SemanticMapping.exact(A, B, subject_type=v.owl_data_property, predicate_modifier=NOT),
    ),
    (
        f.DifferentIndividuals([A, B]),
        SemanticMapping.exact(A, B, subject_type=v.owl_named_individual, predicate_modifier=NOT),
    ),
    (
        None,
        SemanticMapping.exact(
            A, B, subject_type=v.composed_entity_expression, predicate_modifier=NOT
        ),
    ),
    # broad match + no NOT
    (
        f.SubClassOf(A, B),
        _sc_mapping(A, B),
    ),
    (
        f.SubClassOf(A, B),
        _sc_mapping(A, B, subject_type=v.owl_class),
    ),
    (
        f.SubDataPropertyOf(A, B),
        _sc_mapping(A, B, subject_type=v.owl_data_property),
    ),
    (
        f.SubObjectPropertyOf(A, B),
        _sc_mapping(A, B, subject_type=v.owl_object_property),
    ),
    (
        f.SubAnnotationPropertyOf(A, B),
        _sc_mapping(A, B, subject_type=v.owl_annotation_property),
    ),
    (
        f.ClassAssertion(A, B),
        _sc_mapping(A, B, subject_type=v.owl_named_individual, object_type=v.owl_class),
    ),
    (
        None,
        _sc_mapping(A, B, subject_type=v.composite_matching_process),
    ),
    # direct OWL relation usage
    (f.SubClassOf(A, B), _mapping(v.is_a)),
    (f.ClassAssertion(B, A), _mapping(v.rdf_type)),
    (f.EquivalentClasses([A, B]), _mapping(v.equivalent_class)),
    (f.DisjointClasses([A, B]), _mapping(v.equivalent_class).negate()),
    (f.SameIndividual([A, B]), _mapping(v.same_as)),
    (f.DifferentIndividuals([A, B]), _mapping(v.same_as).negate()),
    (None, _mapping(v.part_of)),
    (f.EquivalentObjectProperties([A, B]), _mapping(v.equivalent_property)),
    (
        f.EquivalentObjectProperties([A, B]),
        _mapping(
            v.equivalent_property,
            subject_type=v.owl_object_property,
        ),
    ),
    (
        f.EquivalentDataProperties([A, B]),
        _mapping(
            v.equivalent_property,
            subject_type=v.owl_data_property,
        ),
    ),
    (
        None,  # no concept of equivalent annotation property
        _mapping(
            v.equivalent_property,
            subject_type=v.owl_annotation_property,
        ),
    ),
    (
        f.DisjointObjectProperties([A, B]),
        _mapping(v.equivalent_property).negate(),
    ),
    (
        f.DisjointObjectProperties([A, B]),
        _mapping(v.equivalent_property, subject_type=v.owl_object_property).negate(),
    ),
    (
        f.DisjointDataProperties([A, B]),
        _mapping(v.equivalent_property, subject_type=v.owl_data_property).negate(),
    ),
    (
        None,  # no concept of disjoint annotation property
        _mapping(
            v.equivalent_property,
            subject_type=v.owl_annotation_property,
        ).negate(),
    ),
    (f.SubObjectPropertyOf(A, B), _mapping(v.subproperty_of)),
    (f.SubObjectPropertyOf(A, B), _mapping(v.subproperty_of, subject_type=v.owl_object_property)),
    (f.SubDataPropertyOf(A, B), _mapping(v.subproperty_of, subject_type=v.owl_data_property)),
    (None, _mapping(v.subproperty_of, subject_type=v.owl_class)),
    (
        f.SubAnnotationPropertyOf(A, B),
        _mapping(v.subproperty_of, subject_type=v.owl_annotation_property),
    ),
]


class TestBridge(unittest.TestCase):
    """Test bridge."""

    def test_equivalent_property(self) -> None:
        """Test axioms."""
        for expected, mapping in cases:
            with self.subTest(x=str(mapping)):
                actual = get_owl_bridge_axiom(mapping)
                self.assertEqual(expected, actual)


class TestEndToEnd(unittest.TestCase):
    """Test end-to-end."""

    def setUp(self) -> None:
        """Set up test case."""
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name).joinpath("bridge.ofn")
        self.m = _m(authors=[charlie], confidence=0.8)
        self.converter = TEST_CONVERTER.get_subconverter(
            {
                "chebi",
                "dcterms",
                "mesh",
                "rdfs",
                "pav",
                "orcid",
            }
        )

    def tearDown(self) -> None:
        """Tear down test case."""
        self.directory.cleanup()

    def test_simple(self) -> None:
        """Test end-to-end."""
        write_owl_bridge([self.m], self.path, converter=self.converter, metadata=TEST_MAPPING_SET)
        self.assertEqual(
            dedent("""\
            Prefix(chebi:=<http://purl.obolibrary.org/obo/CHEBI_>)
            Prefix(dcterms:=<http://purl.org/dc/terms/>)
            Prefix(mesh:=<http://id.nlm.nih.gov/mesh/>)
            Prefix(orcid:=<https://orcid.org/>)
            Prefix(pav:=<http://purl.org/pav/>)
            Prefix(rdfs:=<http://www.w3.org/2000/01/rdf-schema#>)

            Ontology(
            Annotation(rdfs:comment "Generated by sssom-pydantic (v0.5.11-dev) on 2026-06-01")
            Annotation(dcterms:license <https://spdx.org/licenses/CC0-1.0>)

            EquivalentClasses(mesh:C000089 chebi:28646)
            )
            """),
            self.path.read_text(),
        )

    def test_declarations(self) -> None:
        """Test end-to-end."""
        write_owl_bridge(
            [self.m],
            self.path,
            converter=self.converter,
            metadata=TEST_MAPPING_SET,
            declarations=True,
        )
        self.assertEqual(
            dedent("""\
            Prefix(chebi:=<http://purl.obolibrary.org/obo/CHEBI_>)
            Prefix(dcterms:=<http://purl.org/dc/terms/>)
            Prefix(mesh:=<http://id.nlm.nih.gov/mesh/>)
            Prefix(orcid:=<https://orcid.org/>)
            Prefix(pav:=<http://purl.org/pav/>)
            Prefix(rdfs:=<http://www.w3.org/2000/01/rdf-schema#>)

            Ontology(
            Annotation(rdfs:comment "Generated by sssom-pydantic (v0.5.11-dev) on 2026-06-01")
            Annotation(dcterms:license <https://spdx.org/licenses/CC0-1.0>)

            Declaration(Class(mesh:C000089))
            Declaration(Class(chebi:28646))
            AnnotationAssertion(rdfs:label mesh:C000089 "ammeline")
            AnnotationAssertion(rdfs:label chebi:28646 "ammeline")
            EquivalentClasses(mesh:C000089 chebi:28646)
            )
            """),
            self.path.read_text(),
        )

    def test_annotations(self) -> None:
        """Test end-to-end."""
        write_owl_bridge(
            [self.m],
            self.path,
            converter=self.converter,
            metadata=TEST_MAPPING_SET,
            mapping_annotations=True,
        )
        self.assertEqual(
            dedent("""\
            Prefix(chebi:=<http://purl.obolibrary.org/obo/CHEBI_>)
            Prefix(dcterms:=<http://purl.org/dc/terms/>)
            Prefix(mesh:=<http://id.nlm.nih.gov/mesh/>)
            Prefix(orcid:=<https://orcid.org/>)
            Prefix(pav:=<http://purl.org/pav/>)
            Prefix(rdfs:=<http://www.w3.org/2000/01/rdf-schema#>)

            Ontology(
            Annotation(rdfs:comment "Generated by sssom-pydantic (v0.5.11-dev) on 2026-06-01")
            Annotation(dcterms:license <https://spdx.org/licenses/CC0-1.0>)

            EquivalentClasses(Annotation(pav:authoredBy orcid:0000-0003-4423-4370) Annotation(sssom:confidence "0.8"^^xsd:decimal) mesh:C000089 chebi:28646)
            Declaration(Class(<http://purl.obolibrary.org/obo/NCBITaxon_9606>))
            AnnotationAssertion(rdfs:label <http://purl.obolibrary.org/obo/NCBITaxon_9606> "human")
            Declaration(NamedIndividual(orcid:0000-0003-4423-4370))
            ClassAssertion(<http://purl.obolibrary.org/obo/NCBITaxon_9606> orcid:0000-0003-4423-4370)
            )
            """),  # noqa:E501
            self.path.read_text(),
        )
