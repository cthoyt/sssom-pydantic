r"""A workflow for evaluating predicted mappings.

The `Ontology Alignment Evaluation Initiative (OAEI)
<https://oaei.ontologymatching.org>`_ has produced and evaluated benchmarks for ontology
mapping software across biology, medicine, ecology, digital humanities, archaeology, and
other disciplines since 2004. In order to submit, developers must ensure their ontology
mapping software consumes ontologies in the `Web Ontology Language (OWL)
<https://www.w3.org/OWL/>`_ format and outputs mappings in the `Expressive and
Declarative Ontology Alignment Language (EDOAL)
<https://moex.gitlabpages.inria.fr/alignapi/edoal.html>`_ format, which can then be
automatically evaluated by the OAEI's `Alignment API and Alignment Server
<https://moex.gitlabpages.inria.fr/alignapi>`_. The results from the last two decades
are linked in the table below.

A criticism of OAEI is that it reuses tasks rather than solving mapping. For example,
the `largebio <https://www.cs.ox.ac.uk/isg/projects/SEALS/oaei/>`_ task for mapping
between the `Foundational Model of Anatomy (FMA) <https://semantic.farm/registry/fma>`_
ontology, `Systematized Nomenclature of Medicine - Clinical Terms (SNOMED-CT)
<https://semantic.farm/registry/snomedct>`_, and United States `National Cancer
Institute Thesaurus (NCIT) <https://semantic.farm/registry/ncit>`_ ran between 2011 and
2022 before being incorporated into the `Bio-ML
<https://krr-oxford.github.io/OAEI-Bio-ML/>`_ task.

Instead, if the mappings produced each year were curated, then the alignments between
each ontology could have been finalized potentially decades ago. This is a heavy
motivation for the community-oriented SSSOM ecosystem which includes community mapping
repositories like `Biomappings <https://github.com/biopragmatics/biomappings>`_ where
predictions can be deposited and software like `SSSOM Curator
<github.com/cthoyt/sssom-curator>`_ that support the interactive curation of predicted
mappings.

This module implements tools for creating and evaluating benchmarks based on mappings in
the `Simple Standard for Sharing Ontological Mappings (SSSOM)
<https://mapping-commons.github.io/sssom>`_.

In the following example, :mod:`sssom_curator` is used to construct lexical predictions
that are evaluated by CLI.

.. code-block:: console

    \$ mkdir test
    \$ cd test
    \$ sssom_curator init --purl-base https://example.org/
    \$ sssom_curator predict lexical mesh maxo
    \$ sssom_pydantic evaluate \
        -i https://w3id.org/biopragmatics/biomappings/sssom/biomappings.sssom.tsv \
        -i data/predictions.sssom.tsv

.. admonition:: OAEI Calls and Publications

    ==== ====================================== ======================================================================
    Year Call                                   Publication
    ==== ====================================== ======================================================================
    2026 https://oaei.ontologymatching.org/2026
    2025 https://oaei.ontologymatching.org/2025
    2024 https://oaei.ontologymatching.org/2024 https://inria.hal.science/hal-04892635/
    2023 https://oaei.ontologymatching.org/2023 https://ora.ox.ac.uk/objects/uuid:e167c7dc-72cd-476a-ba23-d4bcc86e0b60
    2022 https://oaei.ontologymatching.org/2022 https://hal.science/hal-04351729/
    2021 https://oaei.ontologymatching.org/2021 https://openaccess.city.ac.uk/id/eprint/27602/
    2020 https://oaei.ontologymatching.org/2020 https://hal.science/hal-04312966/
    2019 https://oaei.ontologymatching.org/2019 https://openaccess.city.ac.uk/id/eprint/23708/
    2018 https://oaei.ontologymatching.org/2018 https://hal.science/hal-02089249/
    2017 https://oaei.ontologymatching.org/2017 https://air.unimi.it/handle/2434/550707
    2016 https://oaei.ontologymatching.org/2016 https://inria.hal.science/hal-01421833/
    2015 https://oaei.ontologymatching.org/2015 https://hal.science/hal-01254907/
    2014 https://oaei.ontologymatching.org/2014 https://hal.science/hal-01180915/
    2013 https://oaei.ontologymatching.org/2013 https://inria.hal.science/hal-01140027/
    2012 https://oaei.ontologymatching.org/2012 https://inria.hal.science/hal-00768409/
    2011 https://oaei.ontologymatching.org/2011 https://inria.hal.science/hal-00781022/
    2010 https://oaei.ontologymatching.org/2010 https://inria.hal.science/hal-00793276/
    2009 https://oaei.ontologymatching.org/2009 https://inria.hal.science/hal-00794918/
    2008 https://oaei.ontologymatching.org/2008 https://inria.hal.science/hal-00793535/
    2007 https://oaei.ontologymatching.org/2007 https://inria.hal.science/hal-00822893/
    2006 https://oaei.ontologymatching.org/2006 https://ceur-ws.org/Vol-225/paper7.pdf
    2005 https://oaei.ontologymatching.org/2005 https://inria.hal.science/hal-00922283/
    2004 https://oaei.ontologymatching.org/2002 https://inria.hal.science/hal-04892635/
    ==== ====================================== ======================================================================
"""  # noqa:E501

from collections import defaultdict
from collections.abc import Iterable
from typing import NamedTuple, TypeAlias, TypeVar

from curies import Reference
from curies import vocabulary as v
from tqdm import tqdm

from sssom_pydantic import SemanticMapping

__all__ = [
    "Evaluation",
    "Stratification",
    "evaluate_predictions",
    "stratify",
]

X = TypeVar("X")


def _get_v1(
    positive_set: set[X],
    negative_set: set[X],
    predicted_positive_set: set[X],
    predicted_negative_set: set[X],
) -> tuple[int, int, int, int]:
    tp = len(positive_set.intersection(predicted_positive_set))  # true positives
    fn = len(positive_set - predicted_positive_set)  # false negatives
    fp = len(negative_set.intersection(predicted_positive_set))  # false positives
    tn = len(negative_set - predicted_positive_set)  # true negatives
    return tp, fp, fn, tn


#: A string-based hash of mapping based on its subject and object (unordered)
UnorderedSemanticMappingHash: TypeAlias = str


def _subject_object_hash(m: SemanticMapping) -> UnorderedSemanticMappingHash:
    return "-".join(sorted((m.subject.curie, m.object.curie)))


UnorderedPrefixPair: TypeAlias = frozenset[str]

DD: TypeAlias = dict[UnorderedPrefixPair, set[UnorderedSemanticMappingHash]]

PREDICTION_PREDICATES = {
    v.lexical_matching_process,
    v.lexical_similarity_threshold_based_matching_process,
    v.logical_reasoning_matching_process,
    v.semantic_similarity,
    v.structural_matching,
}


class Stratification(NamedTuple):
    """A 4-tuple of mapping dictionaries."""

    positive: DD
    negative: DD
    predicted_positive: DD
    predicted_negative: DD

    def strata(
        self,
    ) -> Iterable[
        tuple[
            UnorderedPrefixPair,
            set[UnorderedSemanticMappingHash],
            set[UnorderedSemanticMappingHash],
            set[UnorderedSemanticMappingHash],
            set[UnorderedSemanticMappingHash],
        ]
    ]:
        """Get all strata."""
        keys = sorted(
            set(self.positive)
            .union(self.negative)
            .union(self.predicted_positive)
            .union(self.predicted_negative)
        )
        for key in keys:
            yield (
                key,
                self.positive.get(key) or set(),
                self.negative.get(key) or set(),
                self.predicted_positive.get(key) or set(),
                self.predicted_negative.get(key) or set(),
            )


#: A dictionary that keeps track of all justifications
#: that aren't pre-configured
UNHANDLED_JUSTIFICATIONS: set[Reference] = set()


def stratify(
    mappings: Iterable[SemanticMapping],
    *,
    accept_unspecified: bool = True,
) -> Stratification:
    """Stratify mappings into a positive, negative, and predicted (positive) set.

    :param mappings: A collection of semantic mappings
    :param accept_unspecified: Whether to consider mappings that do not have an explicit
        justification (i.e., using ``semapv:UnspecifiedMatching``) as having been
        manually curated

    :returns: A stratification tuple

    Semantic mappings are stratified as predicted versus curated based on their mapping
    justification. Predicted semantic mappings have one of the following:

    - ``semapv:LexicalMatching``
    - ``semapv:LexicalSimilarityThresholdMatching``
    - ``semapv:LogicalReasoning``
    - ``semapv:SemanticSimilarityThresholdMatching``
    - ``semapv::StructuralMatching``

    Manually curated semantic mappings have one of the following justifications:

    - ``semapv:ManualMappingCuration``
    - ``semapv:UnspecifiedMatching`` (when opted in with the ``accept_unspecified``
      flag)

    Remaining mapping justifications in the `Semantic Mapping Vocabulary (SEMAPV)
    <https://semantic.farm/registry/semapv>`_ can't be easily categorized. Semantic
    mappings are then subcategorized as positive or negative (i.e., when the predicate
    modifier is set to ``Not``). Note, there are typically no negative predicted
    semantic mappings because software focuses on producing positive semantic mappings.

    If needed, negative mappings can be sampled using techniques based on the open world
    assumption (OWA) or local closed world assumption (LCWA). The `PyKEEN
    <https://github.com/pykeen/pykeen/>`_ graph machine learning library has `detailed
    documentation
    <https://pykeen.readthedocs.io/en/stable/reference/negative_sampling.html>`_ on
    these processes. However, SSSOM-Pydantic focuses on evaluations that don't consider
    predicted negative mappings.
    """
    positive: defaultdict[UnorderedPrefixPair, set[UnorderedSemanticMappingHash]] = defaultdict(set)
    negative: defaultdict[UnorderedPrefixPair, set[UnorderedSemanticMappingHash]] = defaultdict(set)
    predicted_positive: defaultdict[UnorderedPrefixPair, set[UnorderedSemanticMappingHash]] = (
        defaultdict(set)
    )
    predicted_negative: defaultdict[UnorderedPrefixPair, set[UnorderedSemanticMappingHash]] = (
        defaultdict(set)
    )

    # TODO should predicate be accounted for, or should this workflow
    #  just assume squashing has been done correctly first?
    # TODO use broad match and exact match to infer NOT exact match?
    # TODO squash higher relations into exact match?

    acceptable = {v.manual_mapping_curation}
    if accept_unspecified:
        acceptable.add(v.unspecified_matching_process)

    for m in mappings:
        # TODO could also use hash triple to include predicate
        mapping_hash = _subject_object_hash(m)
        prefix_pair: UnorderedPrefixPair = frozenset([m.subject.prefix, m.object.prefix])
        if m.justification in PREDICTION_PREDICATES:
            if m.predicate_modifier is None:
                predicted_positive[prefix_pair].add(mapping_hash)
            else:
                predicted_negative[prefix_pair].add(mapping_hash)
        elif m.justification in acceptable:
            if m.predicate_modifier is None:
                positive[prefix_pair].add(mapping_hash)
            else:
                negative[prefix_pair].add(mapping_hash)
        elif m.justification not in UNHANDLED_JUSTIFICATIONS:
            UNHANDLED_JUSTIFICATIONS.add(m.justification)
            tqdm.write(f"unhandled mapping justification: {m.justification.curie}")

    return Stratification(
        dict(positive),
        dict(negative),
        dict(predicted_positive),
        dict(predicted_negative),
    )


class Evaluation(NamedTuple):
    """An evaluation tuple."""

    completion: float
    accuracy: float
    precision: float
    recall: float
    f1: float


def evaluate_predictions(
    mappings: Iterable[SemanticMapping],
    *,
    tag: str | None = None,
    accept_unspecified: bool = True,
) -> dict[UnorderedPrefixPair, Evaluation]:
    """Evaluate predicted mappings using manually curated positive and negative mappings."""
    stratification = stratify(mappings, accept_unspecified=accept_unspecified)
    rv = {}
    for (
        prefix_pair,
        positive,
        negative,
        predicted_positive,
        predicted_negative,
    ) in stratification.strata():
        try:
            rr = _evaluate_helper(
                positive,
                negative,
                predicted_positive,
                predicted_negative,
                tag=tag,
            )
        except ZeroDivisionError:
            tqdm.write(f"failed to calculate statistics for {prefix_pair}")
        else:
            rv[prefix_pair] = rr
    return rv


def _evaluate_helper(
    positive_set: set[str],
    negative_set: set[str],
    predicted_positive_set: set[str],
    predicted_negative_set: set[str],
    *,
    tag: str | None = None,
) -> Evaluation:
    tp, fp, fn, tn = _get_v1(
        positive_set, negative_set, predicted_positive_set, predicted_negative_set
    )

    predicted_only = len(predicted_positive_set - positive_set - negative_set)
    union_len = len(positive_set.union(predicted_positive_set).union(negative_set))

    msg = f"union={union_len:,}, predicted={predicted_only:,}, {tp=}, {fp=}, {fn=}, {tn=}"
    if tag is not None:
        msg = f"[{tag}] {msg}"
    tqdm.write(msg)

    accuracy = (tp + tn) / (tp + tn + fp + fn)
    recall = tp / (tp + fn)
    precision = tp / (tp + fp)
    f1 = 2 * tp / (2 * tp + fp + fn)
    completion = 1 - predicted_only / len(predicted_positive_set)

    # what is the percentage of curated examples that are positive?
    _positive_percentage = len(positive_set) / (len(positive_set) + len(negative_set))

    return Evaluation(completion, accuracy, precision, recall, f1)
