"""Test bridge."""

import unittest
from typing import Any

import functional_owl as f
from curies import NamableReference
from curies import vocabulary as v
from functional_owl import Axiom

from sssom_pydantic import NOT, SemanticMapping
from sssom_pydantic.contrib.owl_bridge import get_owl_bridge_axiom

A = NamableReference.from_curie("a:1")
B = NamableReference.from_curie("b:1")


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


cases: list[tuple[Axiom, SemanticMapping]] = [
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
    # direct OWL relation usage
]


class TestBridge(unittest.TestCase):
    """Test bridge."""

    def test_equivalent_property(self) -> None:
        """Test axioms."""
        for expected, mapping in cases:
            with self.subTest(x=str(mapping)):
                actual = get_owl_bridge_axiom(mapping)
                if actual is None:
                    raise self.fail(msg="axiom shouldn't be None")
                self.assertEqual(expected.annotations, actual.annotations)
                self.assertEqual(expected, actual)
