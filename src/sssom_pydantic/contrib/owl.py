"""The Simple Standard for Sharing Ontological Mappings (SSSOM) specifies a `transformation <https://mapping-commons.github.io/sssom/dev/spec-formats-owl/>`_ to `Web Ontology Language (OWL) <https://www.w3.org/TR/owl2-overview/>`_.

This enables ontology curators to externalize curation of semantic mappings into SSSOM
TSV files, which better support curators in capturing precise mapping predicates and
provenance metadata. After, SSSOM can be transformed into OWL and merged with their
ontology edit file during release, for example, using the `ROBOT
<https://robot.obolibrary.org/>`_ tool.

:mod:`sssom_pydantic.contrib.owl` implements the transformation into the `Functional OWL
<https://www.w3.org/TR/owl2-syntax/>`_ object model with the :mod:`functional_owl`
package that enables serialization to OWL Functional Notation (OFN), OWL/RDF, and
OWL/XML.

###############
 Example Usage
###############

More specifically, this module implements the transformation from
:class:`sssom_pydantic.SemanticMapping` to :class:`functional_owl.Axiom` in
:func:`get_axiom`.

>>> from curies import Converter
>>> from sssom_pydantic import SemanticMapping
>>> from sssom_pydantic.contrib.owl import get_axiom
>>> converter = Converter.from_prefix_map(
...     {
...         "mesh": "http://id.nlm.nih.gov/mesh/",
...         "CHEBI": "http://purl.obolibrary.org/obo/CHEBI_",
...     }
... )
>>> mapping = SemanticMapping.exact("mesh:C000089", "CHEBI:28646")
>>> get_axiom(mapping, converter).to_funowl()
AnnotationAssertion(skos:exactMatch mesh:C000089 CHEBI:28646)

A collection of semantic mappings and optional mapping set metadata can be written with
:func:`write_owl`.

.. code-block:: python

    from curies import Converter, Reference
    from sssom_pydantic import SemanticMapping, MappingSet
    from sssom_pydantic.examples import TEST_CONVERTER
    from sssom_pydantic.contrib.owl import write_owl

    converter = Converter.from_prefix_map(
        {
            "CHEBI": "http://purl.obolibrary.org/obo/CHEBI_",
            "dcterms": "http://purl.org/dc/terms/",
            "mesh": "http://id.nlm.nih.gov/mesh/",
            "orcid": "https://orcid.org/",
        }
    )
    metadata = MappingSet(
        id="https://example.org/test.sssom.tsv",
        creators=[Reference(prefix="orcid", identifier="0000-0003-4423-4370")],
    )
    mappings = [SemanticMapping.exact("mesh:C000089", "CHEBI:28646")]
    write_owl(
        mappings,
        "test.ofn",
        metadata=metadata,
        converter=converter,
        generation_date_comment=False,
    )

which outputs the following OWL functional notation (OFN):

.. code-block::

    Prefix(CHEBI:=<http://purl.obolibrary.org/obo/CHEBI_>)
    Prefix(dcterms:=<http://purl.org/dc/terms/>)
    Prefix(mesh:=<http://id.nlm.nih.gov/mesh/>)
    Prefix(orcid:=<https://orcid.org/>)

    Ontology(
        Annotation(dcterms:creator orcid:0000-0003-4423-4370)
        AnnotationAssertion(skos:exactMatch mesh:C000089 CHEBI:28646)
    )

This can also be accomplished from the command line with:

.. code-block:: console

    sssom_pydantic owl -i test.sssom.tsv -o test.ofn

######################
 Transformation Rules
######################

This section describes the SSSOM to OWL transformation rules, which are dependent on the
semantic mapping predicate, the subject type, and object type. By default, semantic
mappings are transformed into annotation properties in OWL, with a small number of
special cases that are transformed into logical axioms.

Finally, this section describes two custom workflows for producing OWL bridge files (see
`the Uberon documentation
<https://github.com/obophenotype/uberon/blob/master/docs/bridges.md>`_) and for
upgrading negated semantic mappings to logical axioms.

***********************
 Annotation Properties
***********************

Semantic mappings whose predicates are annotation properties, such as those originating
from SKOS, are transformed using the ``AnnotationAssertion()`` axioms as follows:

====================================== ===========================================================
Semantic Mapping                       Functional OWL Expression
====================================== ===========================================================
``S skos:exactMatch O``                ``AnnotationAssertion(skos:exactMatch S O)``
``S skos:broadMatch O``                ``AnnotationAssertion(skos:broadMatch S O)``
``S skos:narrowMatch O``               ``AnnotationAssertion(skos:narrowMatch S O)``
``S skos:closeMatch O``                ``AnnotationAssertion(skos:closeMatch S O)``
``S skos:relatedMatch O``              ``AnnotationAssertion(skos:relatedMatch S O)``
``S rdfs:seeAlso O``                   ``AnnotationAssertion(skos:seeAlso S O)``
``S oboInOwl:hasDbXref O``             ``AnnotationAssertion(oboInOwl:hasDbXref S O)``
``S IAO:0000118 O`` (alternate term)   ``AnnotationAssertion(IAO:0000118 S O)``
``S IAO:0100001 O`` (term replaced by) ``AnnotationAssertion(IAO:0100001 S O)``
``S semapv:crossSpeciesExactMatch O``  ``AnnotationAssertion(semapv:crossSpeciesExactMatch S O)``
``S semapv:crossSpeciesNarrowMatch O`` ``AnnotationAssertion(semapv:crossSpeciesNarrowMatch S O)``
``S semapv:crossSpeciesBroadMatch O``  ``AnnotationAssertion(semapv:crossSpeciesBroadMatch S O)``
====================================== ===========================================================

In practice, any semantic mapping predicate that doesn't have another transformation
rule associated with it in the following sections `Logical Axioms for Classes`_,
`Logical Axioms for Named Individuals`_, and `Logical Axioms for Properties`_ will get
serialized as a ``AnnotationAssertion()``.

OWL does not have a generic notion of negations, inversions, or complements. Therefore,
the first-class predicate modifier field in SSSOM that represents false information is
annotated onto the annotation assertion using ``Annotation(sssom:predicate_modifier
"Not")`` as in:

============================= =========================================================
Semantic Mapping              Functional Expression
============================= =========================================================
``S not skos:exactMatch O``   ``AnnotationAssertion(Annotation(sssom:predicate_modifier
                              "Not") skos:exactMatch S O)``
``S not skos:broadMatch O``   ``AnnotationAssertion(Annotation(sssom:predicate_modifier
                              "Not") skos:broadMatch S O)``
``S not skos:narrowMatch O``  ``AnnotationAssertion(Annotation(sssom:predicate_modifier
                              "Not") skos:narrowMatch S O)``
``S not skos:closeMatch O``   ``AnnotationAssertion(Annotation(sssom:predicate_modifier
                              "Not") skos:closeMatch S O)``
``S not skos:relatedMatch O`` ``AnnotationAssertion(Annotation(sssom:predicate_modifier
                              "Not") skos:relatedMatch S O)``
``S not rdfs:seeAlso O``      ``AnnotationAssertion(Annotation(sssom:predicate_modifier
                              "Not") skos:seeAlso S O)``
============================= =========================================================

Here's an example SSSOM table containing both a positive and negative semantic mapping
and its transformation into OWL, serialized in OWL functional notation (OFN). The prefix
map and metadata are omitted from both the SSSOM and OWL output for clarity.

=========== ============= =============== ================== ============ ============ ============================
subject_id  subject_label predicate_id    predicate_modifier object_id    object_label mapping_justification
=========== ============= =============== ================== ============ ============ ============================
CHEBI:28646 ammeline      skos:exactMatch                    mesh:C000089 ammeline     semapv:ManualMappingCuration
CHEBI:10057 9H-xanthene   skos:exactMatch Not                mesh:C002563 xanthan gum  semapv:ManualMappingCuration
=========== ============= =============== ================== ============ ============ ============================

.. code-block::

    Ontology(
        Declaration(Class(CHEBI:28646))
        Declaration(Class(CHEBI:10057))
        Declaration(Class(mesh:C000089))
        Declaration(Class(mesh:C002563))

        AnnotationAssertion(skos:exactMatch CHEBI:28646 mesh:C000089)
        AnnotationAssertion(Annotation(sssom:predicate_modifier "Not") skos:exactMatch CHEBI:10057 mesh:C002563)
    )

****************************
 Logical Axioms for Classes
****************************

The following semantic mapping predicates are expanded into OWL logical axioms
describing classes. Any semantic mapping using these predicates have their subject and
object types interpreted as classes.

=========================== ==============================================
Semantic Mapping            Functional OWL Expression
=========================== ==============================================
``S owl:equivalentClass O`` ``EquivalentClasses(S O)``
``S rdfs:subClassOf O``     ``SubClassOf(S O)``
``S owl:complementOf O``    ``EquivalentClasses(S ObjectComplementOf(O))``
``S owl:disjointWith O``    ``DisjointClasses(S O)``
=========================== ==============================================

**************************************
 Logical Axioms for Named Individuals
**************************************

The following semantic mapping predicates are expanded into OWL logical axioms
describing named individuals. Any semantic mapping using these predicates have their
subject and object types interpreted as named indiduals, with the exception being
``rdfs:type``, which infers the object is a class.

========================= =============================
Semantic Mapping          Functional OWL Expression
========================= =============================
``S rdfs:type O``         ``ClassAssertion(O S)``
``S owl:sameAs O``        ``SameIndividual(S O)``
``S owl:differentFrom O`` ``DifferentIndividuals(S O)``
========================= =============================

Here's an example SSSOM table and accompanying OWL output containing examples for each
semantic mapping predicate.

============= ====================== ================= ============= ============ ============================
subject_id    subject_label          predicate_id      object_id     object_label mapping_justification
============= ====================== ================= ============= ============ ============================
ror:04xfq0f34 RWTH Aachen University rdf:type          OBI:0000245   organization semapv:ManualMappingCuration
ror:04fbd2g40 BioNTech (Germany)     owl:sameAs        VO:0004946    BioNTech     semapv:ManualMappingCuration
ror:04fbd2g40 BioNTech (Germany)     owl:differentFrom ror:054q96n74 AstraZeneca  semapv:ManualMappingCuration
============= ====================== ================= ============= ============ ============================

.. code-block::

    Ontology(
        Declaration(Class(OBI:0000245))
        Declaration(NamedIndividual(ror:04xfq0f34))
        Declaration(NamedIndividual(VO:0004946))
        Declaration(NamedIndividual(ror:054q96n74))

        ClassAssertion(OBI:0000245 ror:04xfq0f34)
        SameIndividual(ror:04xfq0f34 VO:0004946)
        DifferentIndividuals(ror:04fbd2g40 ror:054q96n74)
    )

.. note::

    The semantics of ``owl:sameAs`` and ``owl:differentFrom`` are exactly negated,
    meaning that this could be extended to incorporate negated semantic mappings. See
    the section below on Negations_ for more information.

*******************************
 Logical Axioms for Properties
*******************************

The following semantic mapping predicates are expanded into OWL logical axioms
describing properties. The OWL data model differentiates between object properties, data
properties, and annotation properties. Object and data properties are part of the
logical definition of an entity, whereas annotation properties are only informative.

This means that the ``subject_type`` is important in determining the correct functional
OWL expression. When ``subject_type`` is unavailable, this implementation assumes that
the property is an object property.

================================ =================================== ===================
Semantic Mapping                 Functional OWL Expression           Subject Type
================================ =================================== ===================
``S owl:equivalentProperty O``   ``EquivalentObjectProperties(S O)`` object property
``S owl:equivalentProperty O``   ``EquivalentDataProperties(S O)``   data property
``S owl:equivalentProperty O``   does not exist [#f1]_               annotation property
``S owl:propertyDisjointWith O`` ``DisjointObjectProperties(S O)``   object property
``S owl:propertyDisjointWith O`` ``DisjointDataProperties(S O)``     data property
``S owl:propertyDisjointWith O`` doesn't make sense [#f2]_           annotation property
``S rdfs:subPropertyOf O``       ``SubObjectPropertyOf(S O)``        object property
``S rdfs:subPropertyOf O``       ``SubDataPropertyOf(S O)``          data property
``S rdfs:subPropertyOf O``       ``SubAnnotationPropertyOf(S O)``    annotation property
``S owl:inverseOf O``            ``InverseObjectProperties(S O)``    object property
``S owl:inverseOf O``            doesn't make sense [#f3]_           data property
``S owl:inverseOf O``            does not exist [#f4]_               annotation property
================================ =================================== ===================

.. [#f1] This seems like an oversight, because stating that two annotation properties are
    interchangable (e.g., ``dce:creator`` and ``dcterms:creator``) is important

.. [#f2] Because the ``owl:propertyDisjointWith`` is interpreted in a logical way, it doesn't
    make sense for OWL to have a corresponding functional OWL expression for annotation
    properties.

.. [#f3] Literals don't appear as subjects in triples in OWL, so having an inverse for a data
    property doesn't make sense

.. [#f4] Annotation properties can meaningfully be inverted if their range isn't a literal, so
    this seems like an oversight. OWL probably didn't include this since it's only
    informative and not part of a logical definition of an entity.

Here's an example SSSOM table and accompanying OWL output containing examples for some
semantic mapping predicates.

======================== ======================= ======================= ====================== ============================== ========================== ============================
subject_id               subject_label           subject_type            predicate_id           object_id                      object_label               mapping_justification
======================== ======================= ======================= ====================== ============================== ========================== ============================
RO:0018033               is deprotonated form of owl object property     owl:equivalentProperty obo:chebi#is_conjugate_base_of is conjugate base of       semapv:ManualMappingCuration
RO:0018002               myristoylates           owl object property     rdfs:subPropertyOf     RO:0002436                     molecularly interacts with semapv:ManualMappingCuration
oboInOwl:hasBroadSynonym has broad synonym       owl annotation property rdfs:subPropertyOf     IAO:0000118                    alternative label          semapv:ManualMappingCuration
======================== ======================= ======================= ====================== ============================== ========================== ============================

.. code-block::

    Ontology(
        Declaration(ObjectProperty(RO:0018033))
        Declaration(ObjectProperty(RO:0018002))
        Declaration(ObjectProperty(RO:0002436))
        Declaration(ObjectProperty(obo:chebi#is_conjugate_base_of))
        Declaration(ObjectProperty(oboInOwl:hasBroadSynonym))
        Declaration(ObjectProperty(IAO:0000118 ))

        EquivalentObjectProperties(RO:0018033 obo:chebi#is_conjugate_base_of)
        SubObjectPropertyOf(RO:0018002 RO:0002436)
        SubAnnotationPropertyOf(oboInOwl:hasBroadSynonym IAO:0000118)
    )

**********
 Bridging
**********

A bridge ontology is an ontology with logical axioms for merging two or more other
ontologies and enabling joint inference and reasoning. This fits neatly with the notion
of transforming SSSOM to OWL, however, bridge ontologies do not make use of annotation
assertions. Therefore, when constructing a bridge ontology, it is sometimes advantageous
to ascribe stronger logical axioms to weaker semantic mapping predicates like
``skos:exactMatch``, ``skos:narrowMatch``, and ``skos:broadMatch`` that would normally
produce annotation assertions.

This behavior is not part of the SSSOM specification, but was pioneered by `Damien
Goutte-Gattat <https://github.com/gouttegd/>`_ in the incorporation of SSSOM with
Ontology Development Kit (ODK) release workflows and briefly described `here
<https://github.com/INCATools/ontology-development-kit/issues/626#issuecomment-3285032670>`_.
SSSOM Pydantic extends Damien's original idea with additional rules described in the
following table, which are implemented in :func:`get_upgraded_annotation_property`.

.. note::

    In the following table, ``class`` is shorthand for ``rdfs:Class``,
    ``rdfs:Resource``, ``owl:Class``, or ``skos:Concept``.

======================== =================================== ==========================
Semantic Mapping         Functional OWL Expression           Subject Type
======================== =================================== ==========================
``S skos:exactMatch O``  ``EquivalentClasses(S O)``          class or undefined
``S skos:exactMatch O``  ``SameIndividual(S O)``             ``owl:NamedIndividual``
``S skos:exactMatch O``  ``EquivalentObjectProperties(S O)`` ``owl:ObjectProperty`` or
                                                             undefined
``S skos:exactMatch O``  ``EquivalentDataProperties(S O)``   ``owl:DataProperty``
``S skos:exactMatch O``  does not exist                      ``owl:AnnotationProperty``
``S skos:broadMatch O``  ``SubClassOf(S O)``                 class or undefined
``S skos:broadMatch O``  ``ClassAssertion(O, S)``            ``owl:NamedIndividual``
``S skos:broadMatch O``  ``SubObjectPropertyOf(S O)``        ``owl:ObjectProperty`` or
                                                             undefined
``S skos:broadMatch O``  ``SubDataPropertyOf(S O)``          ``owl:DataProperty``
``S skos:broadMatch O``  ``SubAnnotationPropertyOf(S O)``    ``owl:AnnotationProperty``
``O skos:narrowMatch S`` ``SubClassOf(S O)``                 class or undefined
``O skos:narrowMatch S`` ``ClassAssertion(O, S)``            ``owl:NamedIndividual``
``O skos:narrowMatch S`` ``SubObjectPropertyOf(S O)``        ``owl:ObjectProperty`` or
                                                             undefined
``O skos:broadMatch S``  ``SubDataPropertyOf(S O)``          ``owl:DataProperty``
``O skos:broadMatch S``  ``SubAnnotationPropertyOf(S O)``    ``owl:AnnotationProperty``
======================== =================================== ==========================

.. warning::

    The rules between ``skos:broadMatch`` and ``skos:narrowMatch`` are complementary,
    which is why the ``S`` and ``O`` are flipped. In practice, the implementation
    requires applying :func:`sssom_pydantic.process.invert_narrow_matches` to flip all
    narrow matches into broad matches before transforing to OWL.

Adding the ``mode="bridge"`` parameter to :func:`write_owl` opts into this upgrading
behavior to transform the following SSSOM into OWL.

=========== ============= =============== ============ ============ ============================
subject_id  subject_label predicate_id    object_id    object_label mapping_justification
=========== ============= =============== ============ ============ ============================
CHEBI:28646 ammeline      skos:exactMatch mesh:C000089 ammeline     semapv:ManualMappingCuration
=========== ============= =============== ============ ============ ============================

.. code-block::

    Ontology(
        Declaration(Class(CHEBI:28646))
        Declaration(Class(mesh:C000089))

        EquivalentClasses(CHEBI:28646 mesh:C000089)
    )

Similarly, the ``--mode bridge`` option can be passed to the CLI to enable bridging
upgrades.

.. code-block:: console

    sssom_pydantic owl --mode bridge -i test.sssom.tsv -o test.ofn

***********
 Negations
***********

When constructing a bridge ontology, it is sometimes advantageous to ascribe stronger
logical axioms to weaker semantic mapping mappings that include a negative predicate
modifier in conjunction with predicates such as ``skos:exactMatch``,
``skos:narrowMatch``, and ``skos:broadMatch`` that would normally produce annotation
assertions. For example, ``A not exact match B`` could be used to assert ``A
disjointFrom B``.

However, there are a few major caveats to such ascription.

1. If another positive mapping such as ``A subclass of B`` exists, then ``A not exact
   match B`` is a trivial negative mapping, and should be discarded. Otherwise, the
   production of ``A disjointFrom B`` would cause an unsatisfiability. The
   :func:`sssom_pydantic.process.remove_trivial_negative` identifies and removes trivial
   negative mappings.
2. Even the lack of existence of another explicit positive mapping such as ``A subclass
   of B`` doesn't mean that the positive mapping is true. Constructing a logical axiom
   from a negative mapping can only work if based on your curation workflow, you are
   sure that the existence of a negative mapping between ``A`` and ``B`` implies that no
   positive mapping exists.

While these caveats apply to class and property mappings, negative modifiers on mappings
between individuals can be more confidently handled. The negatition of the
``owl:differentFrom`` relation always means that they are the same, and the negation of
``owl:sameAs`` always means they are different.

The following table describes rules for doing this which are implemented in
:func:`get_implied_negation_axiom`.

==================================== =================================== ===================================
Semantic Mapping                     Functional OWL Expression           Subject Type
==================================== =================================== ===================================
``S not skos:exactMatch O``          ``DisjointClasses(S O)``            class or undefined
``S not skos:exactMatch O``          ``DifferentIndividuals(S O)``       ``owl:NamedIndividual``
``S not skos:exactMatch O``          ``DisjointObjectProperties(S O)``   ``owl:ObjectProperty``
``S not skos:exactMatch O``          ``DisjointDataProperties(S O)``     ``owl:DataProperty``
``S not skos:exactMatch O``          does not exist                      ``owl:AnnotationProperty``
``S not owl:equivalentClass O``      ``DisjointClasses(S O)``
``S not owl:disjointWith O``         ``EquivalentClasses(S O)``
``S not owl:differentFrom O``        ``SameIndividual(S O)``
``S not owl:sameAs O``               ``DifferentIndividuals(S O)``
``S not owl:equivalentProperty O``   ``DisjointObjectProperties(S O)``   ``owl:ObjectProperty`` or undefined
``S not owl:equivalentProperty O``   ``DisjointDataProperties(S O)``     ``owl:DataProperty``
``S not owl:equivalentProperty O``   does not exist                      ``owl:AnnotationProperty``
``S not owl:propertyDisjointWith O`` ``EquivalentObjectProperties(S O)`` ``owl:ObjectProperty`` or undefined
``S not owl:propertyDisjointWith O`` ``EquivalentDataProperties(S O)``   ``owl:DataProperty``
``S not owl:propertyDisjointWith O`` does not exist                      ``owl:AnnotationProperty``
==================================== =================================== ===================================

The following example shows how the negative semantic mapping from the section
`Annotation Properties`_ now produces a ``DisjointClasses()`` logical axiom instead of
an ``AnnotationAssertion()`` axiom. It also reuses the examples from `Logical Axioms for
Named Individuals`_ but flips inverts their predicates.

============= ================== ================= ================== ============= ============ ============================
subject_id    subject_label      predicate_id      predicate_modifier object_id     object_label mapping_justification
============= ================== ================= ================== ============= ============ ============================
CHEBI:10057   9H-xanthene        skos:exactMatch   Not                mesh:C002563  xanthan gum  semapv:ManualMappingCuration
ror:04fbd2g40 BioNTech (Germany) owl:differentFrom Not                VO:0004946    BioNTech     semapv:ManualMappingCuration
ror:04fbd2g40 BioNTech (Germany) owl:sameAs        Not                ror:054q96n74 AstraZeneca  semapv:ManualMappingCuration
============= ================== ================= ================== ============= ============ ============================

.. code-block::

    Ontology(
        Declaration(Class(CHEBI:10057))
        Declaration(Class(mesh:C002563))
        Declaration(NamedIndividual(ror:04fbd2g40))
        Declaration(NamedIndividual(ror:054q96n74))
        Declaration(NamedIndividual(VO:0004946))

        DisjointClasses(CHEBI:10057 mesh:C002563)
        SameIndividual(ror:04xfq0f34 VO:0004946)
        DifferentIndividuals(ror:04fbd2g40 ror:054q96n74)
    )

The ``--negation-workflow`` option can be passed to the CLI to enable this workflow when
in bridge mode.

.. code-block:: console

    sssom_pydantic owl --mode bridge --negation-workflow -i test.sssom.tsv -o test.ofn
"""  # noqa:E501

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
from ..constants import guess_class
from ..process import filter_by_confidence, invert_narrow_matches
from ..version import get_version

__all__ = [
    "get_axiom",
    "get_axiom_bridge",
    "get_axioms",
    "get_implied_negation_axiom",
    "get_object_property_axiom",
    "get_upgraded_annotation_property",
    "write_owl",
]

logger = logging.getLogger(__name__)

HUMAN_URI = rdflib.URIRef("http://purl.obolibrary.org/obo/NCBITaxon_9606")

AxiomMode: TypeAlias = Literal["bridge", "inline"]


def write_owl(
    mappings: Iterable[SemanticMapping],
    file: str | Path | TextIO | None = None,
    *,
    converter: curies.Converter,
    mode: AxiomMode | None,
    metadata: MappingSet | None = None,
    minimum_confidence: float | None = None,
    mapping_annotations: bool = False,
    declarations: bool = False,
    allow_arbitrary: bool = False,
    generation_comment: bool = True,
    iri: str | None = None,
    negation_workflow: bool = False,
    **kwargs: Any,
) -> None:
    """Write OWL bridge axioms as an OWL file.

    :param mappings: semantic mappings
    :param file: path to file or a file-like object. If none given, prints to stdout
    :param converter: a converter
    :param mode: Which kinds of axioms should be produced?

        - ``inline`` produces annotation properties as is
        - ``bridge`` applies transformation on SKOS matches to upgrade them to logical
          axioms, where possible, based on
          https://github.com/INCATools/ontology-development-kit/issues/626#issuecomment-3285032670.
          Note, this will automatically invert ``skos:narrowMatch`` mappings
    :param metadata: metadata to annotate to the "ontology"
    :param minimum_confidence: minimum confidence level to keep for exporting as a
        bridge
    :param mapping_annotations: whether to include annotations (extra metadata like
        mapping type, confidence, etc.) on the produced axioms, defaults to false :param
    :param declarations: whether to include declarations (and labels, if available)
    :param allow_arbitrary: When in ``inline`` mode, if set to true, skip mappings with
        predicates that aren't in :data:`curies.vocabulary.extended_match_typedefs`
    :param generation_comment: if true, include an ontology-level annotation for the
        date when this was generated
    :param iri: the IRI for the resulting ontology. if not given, reuses the metadata's
        ID, if available.
    :param negation_workflow: Whether to assume that the curation of a negative exact
        match or equivalence mapping should be used to imply a disjointness axiom.
    :param kwargs: keyword arguments to pass to :func:`functional_owl.write_ontology`.
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
                negation_workflow=negation_workflow,
            )
        ),
        file=file,
        iri=iri if iri is not None else str(metadata.id) if metadata is not None else None,
        annotations=get_metadata_annotations(
            metadata, converter=converter, generation_comment=generation_comment
        )
        if metadata is not None
        else None,
        **kwargs,
    )


def get_metadata_annotations(
    metadata: MappingSet, converter: curies.Converter, *, generation_comment: bool = True
) -> list[Annotation]:
    """Get annotations from mapping set metadata."""
    rv = []
    if generation_comment:
        today = datetime.date.today().isoformat()
        rv.append(
            Annotation(
                v.has_comment,
                LiteralBox(f"Generated by sssom-pydantic (v{get_version()}) on {today}"),
            )
        )
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
    negation_workflow: bool = False,
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
    :param mapping_annotations: whether to include annotations (extra metadata like
        mapping type, confidence, etc.) on the produced axioms, defaults to false
    :param declarations: whether to include declarations for subject and object entities
    :param negation_workflow: Whether to assume that the curation of a negative exact
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

    if mode == "bridge":
        mappings = invert_narrow_matches(mappings, converter=converter)
        func = partial(
            get_axiom_bridge,
            mapping_annotations=mapping_annotations,
            not_implies_disjoint=negation_workflow,
        )
    elif mode == "inline" or mode is None:
        func = partial(
            get_axiom,
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


def get_axiom_bridge(
    mapping: SemanticMapping,
    converter: curies.Converter,
    *,
    mapping_annotations: bool = False,
    not_implies_disjoint: bool = False,
) -> Box | None:
    """Get an OWL bridge axiom from a semantic mapping.

    :param mapping: A semantic mapping
    :param converter: A converter
    :param mapping_annotations: whether to include annotations (extra metadata like
        mapping type, confidence, etc.) on the produced axioms, defaults to false
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
    annotations = get_mapping_annotations(mapping, converter) if mapping_annotations else None
    if mapping.predicate_modifier is None:
        logical_axiom = get_object_property_axiom(mapping, annotations=annotations)
        if logical_axiom is not None:
            return logical_axiom
        return get_upgraded_annotation_property(mapping, annotations=annotations)
    elif not_implies_disjoint:
        return get_implied_negation_axiom(mapping, annotations=annotations)
    return None


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
    """
    if mapping.predicate_modifier is None:
        return None  # don't even bother for non-negative mappings
    match mapping.predicate:
        case v.exact_match:
            if guess_class(mapping.subject_type):
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
        case v.owl_disjoint_with:
            return EquivalentClasses([mapping.subject, mapping.object], annotations=annotations)
        case v.same_as:
            return DifferentIndividuals([mapping.subject, mapping.object], annotations=annotations)
        case v.owl_different_from:
            return SameIndividual([mapping.subject, mapping.object], annotations=annotations)
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
        case v.owl_property_disjoint_with:
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
    return None


def get_upgraded_annotation_property(
    mapping: SemanticMapping, *, annotations: list[Annotation] | None = None
) -> Box | None:
    """Construct a logical axiom from a less precise mapping.

    :param mapping: A semantic mapping
    :param annotations: A list of annotations

    :returns: A logical axiom, if possible

    ======================= =================================== ================================================================================
    Semantic Mapping        Functional OWL Expression           Subject Type
    ======================= =================================== ================================================================================
    ``S skos:exactMatch O`` ``EquivalentClasses(S O)``          ``rdfs:Class``, ``rdfs:Resource``, ``owl:Class``, ``skos:Concept``, or undefined
    ``S skos:exactMatch O`` ``SameIndividual(S O)``             ``S`` is an ``owl:NamedIndividual``
    ``S skos:exactMatch O`` ``EquivalentObjectProperties(S O)`` ``owl:ObjectProperty`` or undefined
    ``S skos:exactMatch O`` ``EquivalentDataProperties(S O)``   ``owl:DataProperty``
    ``S skos:exactMatch O`` does not exist                      ``owl:AnnotationProperty``
    ``S skos:broadMatch O`` ``SubClassOf(S O)``                 ``rdfs:Class``, ``rdfs:Resource``, ``owl:Class``, ``skos:Concept``, or undefined
    ``S skos:broadMatch O`` ``ClassAssertion(O, S)``            ``S`` is an ``owl:NamedIndividual``
    ``S skos:broadMatch O`` ``SubObjectPropertyOf(S O)``        ``owl:ObjectProperty`` or undefined
    ``S skos:broadMatch O`` ``SubDataPropertyOf(S O)``          ``owl:DataProperty``
    ``S skos:broadMatch O`` ``SubAnnotationPropertyOf(S O)``    ``owl:AnnotationProperty``
    ======================= =================================== ================================================================================

    .. note::

        ``skos:broadMatch`` is excluded because the :func:`invert_narrow_matches` should
        be run first
    """  # noqa:E501
    match mapping.predicate:
        case v.exact_match:
            if guess_class(mapping.subject_type):
                return EquivalentClasses([mapping.subject, mapping.object], annotations=annotations)
            elif mapping.subject_type == v.owl_named_individual:
                return SameIndividual([mapping.subject, mapping.object], annotations=annotations)
            elif mapping.subject_type == v.owl_object_property:
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
        case v.broad_match:
            if guess_class(mapping.subject_type):
                return SubClassOf(mapping.subject, mapping.object, annotations=annotations)
            elif mapping.subject_type == v.owl_named_individual and guess_class(
                mapping.object_type
            ):
                return ClassAssertion(mapping.object, mapping.subject, annotations=annotations)
            elif mapping.subject_type == v.owl_object_property:
                return SubObjectPropertyOf(mapping.subject, mapping.object, annotations=annotations)
            elif mapping.subject_type == v.owl_data_property:
                return SubDataPropertyOf(mapping.subject, mapping.object, annotations=annotations)
            elif mapping.subject_type == v.owl_annotation_property:
                return SubAnnotationPropertyOf(
                    mapping.subject, mapping.object, annotations=annotations
                )
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

    ================================ ============================================== ========================================
    Semantic Mapping                 Functional OWL Expression                      Subject Type
    ================================ ============================================== ========================================
    ``S owl:equivalentClass O``      ``EquivalentClasses(S O)``
    ``S rdfs:subClassOf O``          ``SubClassOf(S O)``
    ``S owl:complementOf O``         ``EquivalentClasses(S ObjectComplementOf(O))``
    ``S owl:disjointWith O``         ``DisjointClasses(S O)``
    ``S rdfs:type O``                ``ClassAssertion(O S)``
    ``S owl:sameAs O``               ``SameIndividual(S O)``
    ``S owl:differentFrom O``        ``DifferentIndividuals(S O)``
    ``S owl:equivalentProperty O``   ``EquivalentObjectProperties(S O)``            ``S`` is an object property or undefined
    ``S owl:equivalentProperty O``   ``EquivalentDataProperties(S O)``              ``S`` is a data property
    ``S owl:equivalentProperty O``   does not exist                                 ``S`` is an annotation property
    ``S owl:propertyDisjointWith O`` ``DisjointObjectProperties(S O)``              ``S`` is an object property or undefined
    ``S owl:propertyDisjointWith O`` ``DisjointDataProperties(S O)``                ``S`` is a data property
    ``S owl:propertyDisjointWith O`` does not exist                                 ``S`` is an annotation property
    ``S rdfs:subPropertyOf O``       ``SubObjectPropertyOf(S O)``                   ``S`` is an object property or undefined
    ``S rdfs:subPropertyOf O``       ``SubDataPropertyOf(S O)``                     ``S`` is a data property
    ``S rdfs:subPropertyOf O``       ``SubAnnotationPropertyOf(S O)``               ``S`` is an annotation property
    ``S owl:inverseOf O``            ``InverseObjectProperties(S O)``               ``S`` is an object property or undefined
    ``S owl:inverseOf O``            doesn't make sense                             ``S`` is a data property
    ``S owl:inverseOf O``            does not exist                                 ``S`` is an annotation property
    ================================ ============================================== ========================================
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


def get_axiom(
    mapping: SemanticMapping,
    converter: curies.Converter,
    *,
    allow_arbitrary: bool = False,
    mapping_annotations: bool = False,
) -> Box | None:
    """Get an OWL axiom from a semantic mapping.

    :param mapping: A semantic mapping
    :param converter: A converter
    :param allow_arbitrary: When in ``inline`` mode, if set to true, skip mappings with
        predicates that aren't in :data:`curies.vocabulary.extended_match_typedefs`
    :param mapping_annotations: whether to include annotations (extra metadata like
        mapping type, confidence, etc.) on the produced axioms, defaults to false

    :returns: A functional OWL axiom, if possible

    ========================= ==============================================
    Semantic Mapping          Functional OWL Expression
    ========================= ==============================================
    ``S skos:exactMatch O``   ``AnnotationAssertion(skos:exactMatch S O)``
    ``S skos:broadMatch O``   ``AnnotationAssertion(skos:broadMatch S O)``
    ``S skos:narrowMatch O``  ``AnnotationAssertion(skos:narrowMatch S O)``
    ``S skos:closeMatch O``   ``AnnotationAssertion(skos:closeMatch S O)``
    ``S skos:relatedMatch O`` ``AnnotationAssertion(skos:relatedMatch S O)``
    ``S rdfs:seeAlso O``      ``AnnotationAssertion(skos:seeAlso S O)``
    ========================= ==============================================

    And so on, see :data:`curies.vocabulary.extended_match_typedefs`.
    """
    annotations = get_mapping_annotations(mapping, converter) if mapping_annotations else []
    if mapping.predicate_modifier is not None:
        annotations.append(Annotation("sssom:predicate_modifier", f.LiteralBox("Not")))

    if box := get_object_property_axiom(mapping, annotations=annotations):
        if mapping.predicate_modifier is None:
            return box
        else:
            logger.warning("logical axiom combine with negation %s", mapping.predicate)
            return None
    elif mapping.predicate not in v.extended_match_typedefs and not allow_arbitrary:
        logger.warning("skipping unsupported predicate %s", mapping.predicate)
        return None
    else:
        return AnnotationAssertion(
            mapping.predicate, mapping.subject, mapping.object, annotations=annotations
        )
