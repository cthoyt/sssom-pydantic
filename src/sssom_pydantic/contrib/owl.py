"""Transform SSSOM to OWL based on https://mapping-commons.github.io/sssom/dev/spec-formats-owl/.

This module works by transforming individual mappings into OWL axioms with the
:mod:`functional_owl` package, which can then be written as OWL functional notation,
OWL/RDF, and later, to OWL/XML.

>>> from sssom_pydantic import SemanticMapping
>>> from sssom_pydantic.examples import simple, TEST_CONVERTER
>>> from sssom_pydantic.contrib.owl import get_annotation_axiom
>>> get_annotation_axiom(simple, TEST_CONVERTER)
AnnotationAssertion(skos:exactMatch mesh:C000089 chebi:28646)

- Object Properties from :func:`get_object_property_box`
- Upgrades from :func:`get_upgraded_annotation_property`
- Annotation Properties
- Negation Algorithm from :func:`get_implied_negation`

Implemented in:

- https://github.com/cthoyt/sssom-pydantic/pull/128
- https://github.com/cthoyt/sssom-pydantic/pull/157
- https://github.com/cthoyt/sssom-pydantic/pull/158
- https://github.com/cthoyt/sssom-pydantic/pull/159
"""

from __future__ import annotations

import datetime
import logging
import typing
from collections.abc import Iterable
from functools import partial
from pathlib import Path
from typing import Any, Literal, TextIO, TypeAlias

import curies
import functional_owl as f
import rdflib
from curies import Reference
from curies import vocabulary as v
from functional_owl import (
    Annotation,
    AnnotationAssertion,
    Box,
    ClassAssertion,
    ClassComplementMacro,
    DeclarationType,
    DifferentIndividuals,
    DisjointClasses,
    DisjointDataProperties,
    DisjointObjectProperties,
    EquivalentClasses,
    EquivalentDataProperties,
    EquivalentObjectProperties,
    InverseObjectProperties,
    LiteralBox,
    SameIndividual,
    SubAnnotationPropertyOf,
    SubClassOf,
    SubDataPropertyOf,
    SubObjectPropertyOf,
    write_ontology,
)
from rdflib import XSD

from ..api import MappingSet, SemanticMapping
from ..process import filter_by_confidence, invert_narrow_matches
from ..version import get_version

__all__ = [
    "get_annotation_axiom",
    "get_axioms",
    "get_upgraded_annotation_property",
    "get_implied_negation_axiom",
    "get_object_property_axiom",
    "get_owl_bridge_axiom",
    "write_owl",
]

logger = logging.getLogger(__name__)

HUMAN_URI = rdflib.URIRef("http://purl.obolibrary.org/obo/NCBITaxon_9606")

AxiomMode: TypeAlias = Literal["bridge", "inline"]


def write_owl(
    mappings: Iterable[SemanticMapping],
    path: str | Path | TextIO,
    *,
    converter: curies.Converter,
    mode: AxiomMode | None = None,
    metadata: MappingSet | None = None,
    minimum_confidence: float | None = None,
    mapping_annotations: bool = False,
    declarations: bool = False,
    allow_arbitrary: bool = False,
    **kwargs: Any,
) -> None:
    """Write OWL bridge axioms as an OWL file.

    :param mappings: semantic mappings
    :param path: path to file or a file-like object
    :param converter: a converter
    :param mode: Which kinds of axioms should be produced?

        - ``inline`` produces annotation properties as is
        - ``bridge`` applies transformation on SKOS matches to upgrade them to logical
          axioms, where possible, based on
          https://github.com/INCATools/ontology-development-kit/issues/626#issuecomment-3285032670.
    :param metadata: metadata to annotate to the "ontology"
    :param minimum_confidence: minimum confidence level to keep for exporting as a
        bridge
    :param mapping_annotations: whether to include mapping annotations
    :param declarations: whether to include declarations (and labels, if available)
    :param allow_arbitrary: When in ``inline`` mode, if set to true, skip mappings with
        predicates that aren't in :data:`curies.vocabulary.extended_match_typedefs`
    :param kwargs: keyword arguments to pass to :func:`functional_owl.write_ontology`.

    .. note::

        This function automatically inverts SKOS narrow matches
    """
    # add pav since it's part of the output model
    converter.add_prefix("pav", "http://purl.org/pav/", merge=True)
    converter.add_prefix("dcterms", "http://purl.org/dc/terms/", merge=True)

    write_ontology(
        prefixes=converter,
        axioms=list(
            get_axioms(
                mappings,
                converter=converter,
                mode=mode,
                minimum_confidence=minimum_confidence,
                mapping_annotations=mapping_annotations,
                declarations=declarations,
                allow_arbitrary=allow_arbitrary,
            )
        ),
        file=path,
        annotations=get_metadata_annotations(metadata, converter=converter)
        if metadata is not None
        else None,
        **kwargs,
    )


def get_metadata_annotations(metadata: MappingSet, converter: curies.Converter) -> list[Annotation]:
    """Get annotations from mapping set metadata."""
    today = datetime.date.today().isoformat()
    rv = [
        Annotation(
            v.has_comment, LiteralBox(f"Generated by sssom-pydantic (v{get_version()}) on {today}")
        )
    ]
    if metadata.description:
        rv.append(Annotation(v.has_description, LiteralBox(metadata.description)))
    if metadata.title:
        rv.append(Annotation(v.has_title, LiteralBox(metadata.title)))
    if metadata.version:
        rv.append(Annotation(v.owl_version_info, LiteralBox(metadata.version)))
    if metadata.license:
        rv.append(Annotation(v.has_license, _reference_or_anyuri(converter, str(metadata.license))))
    if metadata.comment:
        rv.append(Annotation(v.has_comment, LiteralBox(metadata.comment)))
    for source_url in metadata.source or []:
        rv.append(Annotation(v.has_source, _reference_or_anyuri(converter, str(source_url))))
    for see_also_url in metadata.see_also or []:
        rv.append(Annotation(v.see_also, _reference_or_anyuri(converter, str(see_also_url))))
    for creator in metadata.creators or []:
        rv.append(Annotation(v.has_creator, creator))
    return rv


def _reference_or_anyuri(converter: curies.Converter, value: str) -> rdflib.Literal | Reference:
    if license_reference := converter.parse_uri(value):
        return license_reference.to_pydantic()
    else:
        return rdflib.Literal(value, datatype=XSD.anyURI)


def get_axioms(
    mappings: Iterable[SemanticMapping],
    converter: curies.Converter,
    *,
    mode: AxiomMode | None = None,
    minimum_confidence: float | None = None,
    mapping_annotations: bool = False,
    declarations: bool = False,
    not_implies_disjoint: bool = False,
    allow_arbitrary: bool = False,
) -> Iterable[Box]:
    """Iterate over OWL axioms from semantic mappings.

    :param mappings: An iterable of semantic mappings
    :param converter: A converter
    :param mode: Which kinds of axioms should be produced?

        - ``inline`` produces annotation properties as is
        - ``bridge`` applies transformation on SKOS matches to upgrade them to logical
          axioms, where possible, based on
          https://github.com/INCATools/ontology-development-kit/issues/626#issuecomment-3285032670.
    :param minimum_confidence: minimum confidence level to keep for exporting bridge
        axioms
    :param mapping_annotations: whether annotations should be added to bridge axioms,
        defaults to false
    :param declarations: whether to include declarations for subject and object entities
    :param not_implies_disjoint: Whether to assume that the curation of a negative exact
        match or equivalence mapping should be used to imply a disjointness axiom.

        .. warning::

            This can be problematic if a negative mapping is trivial, i.e., there exists
            another mapping with a difference predicate between the same subject and
            object that is true. If ``A not exact match B`` and ``A subClassOf B`` are
            both asserted, then implying a disjointness axiom between A and B will cause
            unsatisfiability. To ensure no such trivial negative mappings exist, first
            invoke :func:`sssom_pydantic.process.remove_trivial_negative` on your
            collection of mappings.

    :param allow_arbitrary: When in ``inline`` mode, if set to true, skip mappings with
        predicates that aren't in :data:`curies.vocabulary.extended_match_typedefs`

    :yields: An iterable of functional OWL "boxes"
    """
    if minimum_confidence is not None:
        mappings = filter_by_confidence(mappings, minimum_confidence)

    if mode is None or mode == "bridge":
        mappings = invert_narrow_matches(mappings, converter=converter)
        func = partial(
            get_owl_bridge_axiom,
            mapping_annotations=mapping_annotations,
            not_implies_disjoint=not_implies_disjoint,
        )
    elif mode == "inline":
        func = partial(
            get_annotation_axiom,
            mapping_annotations=mapping_annotations,
            allow_arbitrary=allow_arbitrary,
        )
    else:
        raise ValueError(f"invalid mode {mode}. use one of {typing.get_args(AxiomMode)}")

    authors: set[Reference] = set()
    for m in mappings:
        axiom = func(m, converter)
        if axiom is None:
            continue
        if declarations:
            yield f.Declaration(m.subject, _type_to_declaration_type(m.subject_type, m.predicate))
            yield f.Declaration(m.object, _type_to_declaration_type(m.object_type, m.predicate))
            if m.subject.name is not None:
                yield f.LabelMacro(m.subject, m.subject.name)
            if m.object.name is not None:
                yield f.LabelMacro(m.object, m.object.name)
        if m.authors:
            authors.update(m.authors)
        yield axiom

    if mapping_annotations and authors:
        yield f.Declaration(HUMAN_URI, "Class")
        yield f.LabelMacro(HUMAN_URI, "human")
        for author in sorted(authors):
            yield f.Declaration(author, "NamedIndividual")
            yield f.ClassAssertion(HUMAN_URI, author)
            if author_name := getattr(author, "name", None):
                yield f.LabelMacro(author, author_name)


PREDICATE_TO_DEFAULT_DECLARATION_TYPE: dict[Reference, DeclarationType] = {
    v.exact_match: "Class",
    v.broad_match: "Class",
    v.narrow_match: "Class",
    v.equivalent_class: "Class",
    v.equivalent_property: "ObjectProperty",
    v.subproperty_of: "ObjectProperty",
    v.is_a: "Class",
    v.rdf_type: "NamedIndividual",
    v.same_as: "NamedIndividual",
    v.owl_different_from: "NamedIndividual",
    v.owl_disjoint_with: "Class",
    v.owl_complement_of: "Class",
    v.owl_inverse_of: "ObjectProperty",
    v.owl_property_disjoint_with: "ObjectProperty",
}

# see https://mapping-commons.github.io/sssom/dev/EntityTypeEnum/
SIDE_TYPE_REFERENCE_TO_DECLARATION_TYPE: dict[Reference, DeclarationType] = {
    v.owl_class: "Class",
    v.owl_object_property: "ObjectProperty",
    v.owl_data_property: "DataProperty",
    v.owl_annotation_property: "AnnotationProperty",
    v.owl_named_individual: "NamedIndividual",
    v.rdfs_datatype: "Datatype",
    v.rdfs_class: "Class",
    # the following are not perfect, but usually good enough
    v.skos_concept: "Class",
    v.rdfs_resource: "Class",
    v.rdfs_property: "ObjectProperty",
    # the following don't have obvious mappings
    # v.rdfs_literal,
    # v.composed_entity_expression,
}


def _type_to_declaration_type(
    type_reference: Reference | None, predicate: Reference
) -> DeclarationType:
    if type_reference is None:
        return PREDICATE_TO_DEFAULT_DECLARATION_TYPE.get(predicate, "Class")
    return SIDE_TYPE_REFERENCE_TO_DECLARATION_TYPE.get(type_reference, "Class")


def get_owl_bridge_axiom(
    m: SemanticMapping,
    converter: curies.Converter,
    *,
    mapping_annotations: bool = False,
    not_implies_disjoint: bool = False,
) -> Box | None:
    """Get an OWL bridge axiom from a semantic mapping.

    :param m: A semantic mapping
    :param converter: A converter
    :param mapping_annotations: Whether to include SSSOM metadata as annotations on the
        produced axioms
    :param not_implies_disjoint: Whether to assume that the curation of a negative exact
        match or equivalence mapping should be used to imply a disjointness axiom.

        .. warning::

            This can be problematic if a negative mapping is trivial, i.e., there exists
            another mapping with a difference predicate between the same subject and
            object that is true. If ``A not exact match B`` and ``A subClassOf B`` are
            both asserted, then implying a disjointness axiom between A and B will cause
            unsatisfiability. To ensure no such trivial negative mappings exist, first
            invoke :func:`sssom_pydantic.process.remove_trivial_negative` on your
            collection of mappings.


    :returns: An OWL axiom, if one can be constructed.
    """
    anns = get_mapping_annotations(m, converter) if mapping_annotations else None
    if m.predicate_modifier is None:
        logical_axiom = get_object_property_axiom(m, annotations=anns)
        if logical_axiom is not None:
            return logical_axiom
        return get_upgraded_annotation_property(m, anns)
    elif not_implies_disjoint:
        return get_implied_negation_axiom(m, annotations=anns)
    return None


def _is_class(r: curies.Reference | None) -> bool:
    return (
        r is None
        or r == v.owl_class
        or r == v.skos_concept
        or r == v.rdfs_class
        or r == v.rdfs_datatype
    )


def get_mapping_annotations(
    mapping: SemanticMapping, converter: curies.Converter
) -> list[Annotation]:
    """Get annotations from a semantic mapping."""
    return list(_iter_annotations(mapping, converter))


def _iter_annotations(
    mapping: SemanticMapping, converter: curies.Converter
) -> Iterable[Annotation]:
    yield Annotation("sssom:mapping_justification", mapping.justification)
    for author in mapping.authors or []:
        yield Annotation("pav:authoredBy", author)
    if mapping.confidence is not None:
        yield Annotation("sssom:confidence", f.LiteralBox(mapping.confidence))
    if mapping.mapping_tool is not None:
        pass
    if mapping.license is not None:
        yield Annotation(v.has_license, _reference_or_anyuri(converter, mapping.license))
    for creator in mapping.creators or []:
        yield Annotation(v.has_creator, creator)
    for reviewer in mapping.reviewers or []:
        yield Annotation("sssom:reviewer_id", reviewer)
    if mapping.mapping_date is not None:
        yield Annotation("dcterms:created", mapping.mapping_date)
    if mapping.publication_date:
        yield Annotation("dcterms:issued", mapping.publication_date)
    if mapping.comment:
        yield Annotation(v.has_comment, f.LiteralBox(mapping.comment))
    for see_also_uri in mapping.see_also or []:
        yield Annotation(v.see_also, _reference_or_anyuri(converter, see_also_uri))
    # TODO remaining


def get_implied_negation_axiom(
    mapping: SemanticMapping, *, annotations: list[Annotation] | None = None
) -> Box | None:
    """Construct an implied negation.

    :param mapping: A semantic mapping
    :param annotations: A list of annotations

    :returns: A logical axiom, if possible

    ================================== ================================== =================================================================================
    Predicate                          Functional Expression              Condition
    ================================== ================================== =================================================================================
    ``S not skos:exactMatch O``        ``DisjointClasses(S, O)``          ``S`` is a ``rdfs:Class``, ``rdfs:Resource``, ``owl:Class``, ``skos:Concept``, or
                                                                          undefined
    ``S not skos:exactMatch O``        ``DifferentIndividuals(S, O)``     ``S`` is an ``owl:NamedIndividual``
    ``S not skos:exactMatch O``        ``DisjointObjectProperties(S, O)`` ``S`` is a ``owl:ObjectProperty`` or undefined
    ``S not skos:exactMatch O``        ``DisjointDataProperties(S, O)``   ``S`` is a ``owl:DataProperty``
    ``S not skos:exactMatch O``        does not exist                     ``S`` is a ``owl:AnnotationProperty``
    ``S not owl:equivalentClass O``    ``DisjointClasses(S, O)``
    ``S not owl:sameAs O``             ``DifferentIndividuals(S, O)``
    ``S not owl:equivalentProperty O`` ``DisjointObjectProperties(S, O)`` ``S`` is an ``owl:ObjectProperty`` or undefined
    ``S not owl:equivalentProperty O`` ``DisjointDataProperties(S, O)``   ``S`` is an ``owl:DataProperty``
    ``S not owl:equivalentProperty O`` does not exist                     ``S`` is an ``owl:AnnotationProperty``
    ================================== ================================== =================================================================================
    """  # noqa:E501
    if mapping.predicate_modifier is None:
        return None  # don't even bother for non-negative mappings
    match mapping.predicate:
        case v.exact_match:
            if _is_class(mapping.subject_type):
                return DisjointClasses([mapping.subject, mapping.object], annotations=annotations)
            elif mapping.subject_type == v.owl_named_individual:
                return DifferentIndividuals(
                    [mapping.subject, mapping.object], annotations=annotations
                )
            elif mapping.subject_type == v.owl_object_property:
                return DisjointObjectProperties(
                    [mapping.subject, mapping.object], annotations=annotations
                )
            elif mapping.subject_type == v.owl_data_property:
                return DisjointDataProperties(
                    [mapping.subject, mapping.object], annotations=annotations
                )
            # note, there's no concept of DisjointAnnotationProperties since
            # these aren't used for logical axioms
            else:
                return None
        case v.equivalent_class:
            return DisjointClasses([mapping.subject, mapping.object], annotations=annotations)
        case v.same_as:
            return DifferentIndividuals([mapping.subject, mapping.object], annotations=annotations)
        case v.equivalent_property:
            if mapping.subject_type is None or mapping.subject_type == v.owl_object_property:
                return DisjointObjectProperties(
                    [mapping.subject, mapping.object], annotations=annotations
                )
            elif mapping.subject_type == v.owl_data_property:
                return DisjointDataProperties(
                    [mapping.subject, mapping.object], annotations=annotations
                )
            # note, there's no concept of DisjointAnnotationProperties since
            # these aren't used for logical axioms
            else:
                return None
    return None


def get_upgraded_annotation_property(
    m: SemanticMapping, anns: list[Annotation] | None = None
) -> Box | None:
    """Construct a logical axiom from a less precise mapping.

    :param mapping: A semantic mapping
    :param annotations: A list of annotations

    :returns: A logical axiom, if possible

    ======================= ==================================== =================================================================================
    Predicate               Functional Expression                Condition
    ======================= ==================================== =================================================================================
    ``S skos:exactMatch O`` ``EquivalentClasses(S, O)``          ``S`` is a ``rdfs:Class``, ``rdfs:Resource``, ``owl:Class``, ``skos:Concept``, or
                                                                 undefined
    ``S skos:exactMatch O`` ``SameIndividual(S, O)``             ``S`` is an ``owl:NamedIndividual``
    ``S skos:exactMatch O`` ``EquivalentObjectProperties(S, O)`` ``S`` is a ``owl:ObjectProperty`` or undefined
    ``S skos:exactMatch O`` ``EquivalentDataProperties(S, O)``   ``S`` is a ``owl:DataProperty``
    ``S skos:exactMatch O`` does not exist                       ``S`` is a ``owl:AnnotationProperty``
    ``S skos:broadMatch O`` ``SubClassOf(S, O)``                 ``S`` is a ``rdfs:Class``, ``rdfs:Resource``, ``owl:Class``, ``skos:Concept``, or
                                                                 undefined
    ``S skos:broadMatch O`` ``ClassAssertion(O, S)``             ``S`` is an ``owl:NamedIndividual`` and ``O`` is a class
    ``S skos:broadMatch O`` ``SubObjectPropertyOf(S, O)``        ``S`` is a ``owl:ObjectProperty`` or undefined
    ``S skos:broadMatch O`` ``SubDataPropertyOf(S, O)``          ``S`` is a ``owl:DataProperty``
    ``S skos:broadMatch O`` ``SubAnnotationPropertyOf(S, O)``    ``S`` is a ``owl:AnnotationProperty``
    ======================= ==================================== =================================================================================

    .. note::

        ``skos:broadMatch`` is excluded because the :func:`invert_narrow_matches` should
        be run first
    """  # noqa:E501
    match m.predicate:
        case v.exact_match:
            if _is_class(m.subject_type):
                return EquivalentClasses([m.subject, m.object], annotations=anns)
            elif m.subject_type == v.owl_named_individual:
                return SameIndividual([m.subject, m.object], annotations=anns)
            elif m.subject_type == v.owl_object_property:
                return EquivalentObjectProperties([m.subject, m.object], annotations=anns)
            elif m.subject_type == v.owl_data_property:
                return EquivalentDataProperties([m.subject, m.object], annotations=anns)
            # note, there's no concept of EquivalentAnnotationProperties since
            # these aren't used for logical axioms
            else:
                return None
        case v.broad_match:
            if _is_class(m.subject_type):
                return SubClassOf(m.subject, m.object, annotations=anns)
            elif m.subject_type == v.owl_named_individual and _is_class(m.object_type):
                return ClassAssertion(m.object, m.subject, annotations=anns)
            elif m.subject_type == v.owl_object_property:
                return SubObjectPropertyOf(m.subject, m.object, annotations=anns)
            elif m.subject_type == v.owl_data_property:
                return SubDataPropertyOf(m.subject, m.object, annotations=anns)
            elif m.subject_type == v.owl_annotation_property:
                return SubAnnotationPropertyOf(m.subject, m.object, annotations=anns)
            else:
                return None
        # narrow match - excluded because inversion should be done before
        # close match, related match, see also, etc. - excluded because not logical
    return None


def get_object_property_axiom(
    mapping: SemanticMapping, *, annotations: list[Annotation] | None = None
) -> Box | None:
    """Extract a logical axiom, isomorphically.

    :param mapping: A semantic mapping
    :param annotations: A list of annotations

    :returns: A logical axiom, if possible

    ================================ =============================================== ========================================
    Predicate                        Functional Expression                           Condition
    ================================ =============================================== ========================================
    ``S owl:equivalentClass O``      ``EquivalentClasses(S, O)``
    ``S rdfs:subClassOf O``          ``SubClassOf(S, O)``
    ``S owl:complementOf O``         ``EquivalentClasses(S, ObjectComplementOf(O))``
    ``S rdfs:type O``                ``ClassAssertion(O, S)``
    ``S owl:sameAs O``               ``SameIndividual(S, O)``
    ``S owl:differentFrom O``        ``DifferentIndividuals(S, O)``
    ``S owl:equivalentProperty O``   ``EquivalentObjectProperties(S, O)``            ``S`` is an object property or undefined
    ``S owl:equivalentProperty O``   ``EquivalentDataProperties(S, O)``              ``S`` is a data property
    ``S owl:equivalentProperty O``   does not exist                                  ``S`` is an annotation property
    ``S owl:propertyDisjointWith O`` ``DisjointObjectProperties(S, O)``              ``S`` is an object property or undefined
    ``S owl:propertyDisjointWith O`` ``DisjointDataProperties(S, O)``                ``S`` is a data property
    ``S owl:propertyDisjointWith O`` does not exist                                  ``S`` is an annotation property
    ``S rdfs:subPropertyOf O``       ``SubObjectPropertyOf(S, O)``                   ``S`` is an object property or undefined
    ``S rdfs:subPropertyOf O``       ``SubDataPropertyOf(S, O)``                     ``S`` is a data property
    ``S rdfs:subPropertyOf O``       ``SubAnnotationPropertyOf(S, O)``               ``S`` is an annotation property
    ``S owl:inverseOf O``            ``InverseObjectProperties(S, O)``               ``S`` is an object property or undefined
    ``S owl:inverseOf O``            doesn't make sense                              ``S`` is a data property
    ``S owl:inverseOf O``            does not exist                                  ``S`` is an annotation property
    ================================ =============================================== ========================================
    """  # noqa:E501
    match mapping.predicate:
        # Classes
        case v.equivalent_class:
            return EquivalentClasses([mapping.subject, mapping.object], annotations=annotations)
        case v.owl_disjoint_with:
            return DisjointClasses([mapping.subject, mapping.object], annotations=annotations)
        case v.is_a:
            return SubClassOf(mapping.subject, mapping.object, annotations=annotations)
        case v.owl_complement_of:  # sort of like an inverse for classes
            return ClassComplementMacro(mapping.subject, mapping.object, annotations=annotations)
        case v.rdf_type:
            return ClassAssertion(mapping.object, mapping.subject, annotations=annotations)
        # Individuals
        case v.same_as:
            return SameIndividual([mapping.subject, mapping.object], annotations=annotations)
        case v.owl_different_from:
            return DifferentIndividuals([mapping.subject, mapping.object], annotations=annotations)
        # Properties
        case v.equivalent_property:
            if mapping.subject_type is None or mapping.subject_type == v.owl_object_property:
                return EquivalentObjectProperties(
                    [mapping.subject, mapping.object], annotations=annotations
                )
            elif mapping.subject_type == v.owl_data_property:
                return EquivalentDataProperties(
                    [mapping.subject, mapping.object], annotations=annotations
                )
            # note, there's no concept of EquivalentAnnotationProperties since
            # these aren't used for logical axioms
            else:
                return None
        case v.owl_property_disjoint_with:
            if mapping.subject_type is None or mapping.subject_type == v.owl_object_property:
                return DisjointObjectProperties(
                    [mapping.subject, mapping.object], annotations=annotations
                )
            elif mapping.subject_type == v.owl_data_property:
                return DisjointDataProperties(
                    [mapping.subject, mapping.object], annotations=annotations
                )
            else:
                return None
        case v.subproperty_of:
            if mapping.subject_type is None or mapping.subject_type == v.owl_object_property:
                return SubObjectPropertyOf(mapping.subject, mapping.object, annotations=annotations)
            elif mapping.subject_type == v.owl_data_property:
                return SubDataPropertyOf(mapping.subject, mapping.object, annotations=annotations)
            elif mapping.subject_type == v.owl_annotation_property:
                return SubAnnotationPropertyOf(
                    mapping.subject, mapping.object, annotations=annotations
                )
        case v.owl_inverse_of:
            return InverseObjectProperties(mapping.subject, mapping.object, annotations=annotations)

    return None


def get_annotation_axiom(
    m: SemanticMapping,
    converter: curies.Converter,
    *,
    allow_arbitrary: bool = False,
    mapping_annotations: bool = False,
) -> Box | None:
    """Get an OWL bridge axiom from a semantic mapping."""
    anns = get_mapping_annotations(m, converter) if mapping_annotations else []
    if m.predicate_modifier is not None:
        anns.append(Annotation("sssom:predicate_modifier", f.LiteralBox("Not")))

    if box := get_object_property_axiom(m, annotations=anns):
        if m.predicate_modifier is None:
            return box
        else:
            logger.warning("logical axiom combine with negation %s", m.predicate)
            return None
    elif m.predicate not in v.extended_match_typedefs and not allow_arbitrary:
        logger.warning("skipping unsupported predicate %s", m.predicate)
        return None
    else:
        return AnnotationAssertion(m.predicate, m.subject, m.object, annotations=anns)
