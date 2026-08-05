"""Test bridge."""

import datetime
import tempfile
import unittest
from collections.abc import Iterable
from pathlib import Path
from textwrap import dedent
from typing import Any

import functional_owl as f
import rdflib
from curies import NamableReference, Reference
from curies import vocabulary as v
from curies.vocabulary import charlie
from functional_owl import Axiom, Box
from pydantic import AnyUrl
from rdflib import XSD

from sssom_pydantic import NOT, MappingSet, SemanticMapping
from sssom_pydantic.contrib.owl_bridge import (
    get_mapping_annotations,
    get_metadata_annotations,
    get_owl_bridge_axiom,
    write_owl_bridge,
)
from sssom_pydantic.version import get_version
from tests.cases import TEST_CONVERTER, TEST_MAPPING_SET, _m

A = NamableReference.from_curie("a:1")
B = NamableReference.from_curie("b:1")
TODAY = datetime.date.today().isoformat()
VERSION = get_version()


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
    (f.DifferentIndividuals([A, B]), _mapping(v.owl_different_from)),
    (f.DisjointClasses([A, B]), _mapping(v.owl_disjoint_with)),
    (f.InverseObjectProperties(A, B), _mapping(v.owl_inverse_of)),
    (f.DisjointObjectProperties([A, B]), _mapping(v.owl_property_disjoint_with)),
    (
        f.DisjointObjectProperties([A, B]),
        _mapping(v.owl_property_disjoint_with, subject_type=v.owl_object_property),
    ),
    (
        f.DisjointDataProperties([A, B]),
        _mapping(v.owl_property_disjoint_with, subject_type=v.owl_data_property),
    ),
    (None, _mapping(v.owl_property_disjoint_with, subject_type=v.owl_annotation_property)),
    (None, _mapping(v.owl_inverse_of).negate()),
]


class TestBridge(unittest.TestCase):
    """Test bridge."""

    def test_equivalent_property(self) -> None:
        """Test axioms."""
        for expected, mapping in cases:
            with self.subTest(x=str(mapping)):
                actual = get_owl_bridge_axiom(
                    mapping, not_implies_disjoint=True, converter=TEST_CONVERTER
                )
                self.assertEqual(expected, actual)

    def test_no_implications(self) -> None:
        """Test when negation implemention is turned off."""
        self.assertIsNone(
            get_owl_bridge_axiom(
                _mapping(v.exact_match).negate(),
                not_implies_disjoint=False,
                converter=TEST_CONVERTER,
            )
        )


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
                "spdx",
            }
        )

    def tearDown(self) -> None:
        """Tear down test case."""
        self.directory.cleanup()

    def test_simple(self) -> None:
        """Test end-to-end."""
        write_owl_bridge([self.m], self.path, converter=self.converter, metadata=TEST_MAPPING_SET)
        self.assertEqual(
            dedent(f"""\
            Prefix(chebi:=<http://purl.obolibrary.org/obo/CHEBI_>)
            Prefix(dcterms:=<http://purl.org/dc/terms/>)
            Prefix(mesh:=<http://id.nlm.nih.gov/mesh/>)
            Prefix(orcid:=<https://orcid.org/>)
            Prefix(pav:=<http://purl.org/pav/>)
            Prefix(rdfs:=<http://www.w3.org/2000/01/rdf-schema#>)
            Prefix(spdx:=<https://spdx.org/licenses/>)

            Ontology(
            Annotation(rdfs:comment "Generated by sssom-pydantic (v{VERSION}) on {TODAY}")
            Annotation(dcterms:license spdx:CC0-1.0)

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
            dedent(f"""\
            Prefix(chebi:=<http://purl.obolibrary.org/obo/CHEBI_>)
            Prefix(dcterms:=<http://purl.org/dc/terms/>)
            Prefix(mesh:=<http://id.nlm.nih.gov/mesh/>)
            Prefix(orcid:=<https://orcid.org/>)
            Prefix(pav:=<http://purl.org/pav/>)
            Prefix(rdfs:=<http://www.w3.org/2000/01/rdf-schema#>)
            Prefix(spdx:=<https://spdx.org/licenses/>)

            Ontology(
            Annotation(rdfs:comment "Generated by sssom-pydantic (v{VERSION}) on {TODAY}")
            Annotation(dcterms:license spdx:CC0-1.0)

            Declaration(Class(mesh:C000089))
            Declaration(Class(chebi:28646))
            AnnotationAssertion(rdfs:label mesh:C000089 "ammeline")
            AnnotationAssertion(rdfs:label chebi:28646 "ammeline")
            EquivalentClasses(mesh:C000089 chebi:28646)
            )
            """),
            self.path.read_text(),
        )

    def assert_boxes_equal(self, expected: list[Box], actual: Iterable[Box] | None) -> None:
        """Assert that a sequence of boxes are equal."""
        if actual is None:
            self.fail()
        self.assertEqual(
            [b.to_funowl() for b in expected],
            [b.to_funowl() for b in actual],
        )

    def test_mapping_annotations(self) -> None:
        """Test construction of annotations for a semantic mapping."""
        mapping_date = datetime.date(2026, 8, 5)
        publication_date = datetime.date(2026, 8, 6)
        mapping = SemanticMapping(
            subject=A,
            predicate=v.exact_match,
            object=B,
            justification=v.unspecified_matching_process,
            confidence=0.8,
            license="https://spdx.org/licenses/CC0-1.0",
            creators=[charlie],
            authors=[charlie],
            mapping_date=mapping_date,
            publication_date=publication_date,
            comment="test comment",
            see_also=["https://example.org/also.tsv"],
        )
        self.assert_boxes_equal(
            [
                f.Annotation("sssom:mapping_justification", v.unspecified_matching_process),
                f.Annotation(v.has_author, charlie),
                f.Annotation("sssom:confidence", 0.8),
                f.Annotation(v.has_license, Reference(prefix="spdx", identifier="CC0-1.0")),
                f.Annotation(v.has_creator, charlie),
                f.Annotation("dcterms:created", mapping_date),
                f.Annotation("dcterms:issued", publication_date),
                f.Annotation(v.has_comment, f.LiteralBox("test comment")),
                f.Annotation(
                    v.see_also, rdflib.Literal("https://example.org/also.tsv", datatype=XSD.anyURI)
                ),
            ],
            get_mapping_annotations(mapping, converter=self.converter),
        )

    def test_mapping_set_annotations(self) -> None:
        """Test construction of annotations for a mapping set."""
        ms = MappingSet(
            id=AnyUrl("https://example.org/test.tsv"),
            description="test description",
            title="test title",
            version="1",
            comment="test comment",
            source=[AnyUrl("https://example.org/source.tsv")],
            see_also=[AnyUrl("https://example.org/also.tsv")],
            creators=[charlie],
        )
        self.assert_boxes_equal(
            [
                f.Annotation(
                    v.has_comment,
                    f.LiteralBox(f"Generated by sssom-pydantic (v{VERSION}) on {TODAY}"),
                ),
                f.Annotation(v.has_description, f.LiteralBox("test description")),
                f.Annotation(v.has_title, f.LiteralBox("test title")),
                f.Annotation(v.owl_version_info, f.LiteralBox("1")),
                f.Annotation(v.has_comment, f.LiteralBox("test comment")),
                f.Annotation(
                    v.has_source,
                    rdflib.Literal("https://example.org/source.tsv", datatype=XSD.anyURI),
                ),
                f.Annotation(
                    v.see_also, rdflib.Literal("https://example.org/also.tsv", datatype=XSD.anyURI)
                ),
                f.Annotation(v.has_creator, charlie),
            ],
            get_metadata_annotations(ms, converter=self.converter),
        )

    def test_annotations(self) -> None:
        """Test end-to-end."""
        unmappable = SemanticMapping(
            subject="mesh:D12345",
            predicate=v.close_match,
            object="chebi:1234",
            justification=v.unspecified_matching_process,
        )
        write_owl_bridge(
            [self.m, unmappable],
            self.path,
            converter=self.converter,
            metadata=TEST_MAPPING_SET,
            mapping_annotations=True,
        )
        self.assertEqual(
            dedent(f"""\
            Prefix(chebi:=<http://purl.obolibrary.org/obo/CHEBI_>)
            Prefix(dcterms:=<http://purl.org/dc/terms/>)
            Prefix(mesh:=<http://id.nlm.nih.gov/mesh/>)
            Prefix(orcid:=<https://orcid.org/>)
            Prefix(pav:=<http://purl.org/pav/>)
            Prefix(rdfs:=<http://www.w3.org/2000/01/rdf-schema#>)
            Prefix(spdx:=<https://spdx.org/licenses/>)

            Ontology(
            Annotation(rdfs:comment "Generated by sssom-pydantic (v{VERSION}) on {TODAY}")
            Annotation(dcterms:license spdx:CC0-1.0)

            EquivalentClasses(Annotation(sssom:mapping_justification semapv:ManualMappingCuration) Annotation(pav:authoredBy orcid:0000-0003-4423-4370) Annotation(sssom:confidence "0.8"^^xsd:decimal) mesh:C000089 chebi:28646)
            Declaration(Class(<http://purl.obolibrary.org/obo/NCBITaxon_9606>))
            AnnotationAssertion(rdfs:label <http://purl.obolibrary.org/obo/NCBITaxon_9606> "human")
            Declaration(NamedIndividual(orcid:0000-0003-4423-4370))
            ClassAssertion(<http://purl.obolibrary.org/obo/NCBITaxon_9606> orcid:0000-0003-4423-4370)
            AnnotationAssertion(rdfs:label orcid:0000-0003-4423-4370 "Charles Tapley Hoyt")
            )
            """),  # noqa:E501
            self.path.read_text(),
        )
