r"""A workflow for evaluating mapping predictions against manually curated mappings.

The `Ontology Alignment Evaluation Initiative (OAEI)
<https://oaei.ontologymatching.org>`_ has produced and evaluated benchmarks for ontology
mapping software across biology, medicine, ecology, digital humanities, archaeology, and
other disciplines since 2004. In order to submit, developers must ensure their ontology
mapping software consumes ontologies in the `Web Ontology Language (OWL)
<https://www.w3.org/OWL/>`_ format and outputs mappings in the `Expressive and
Declarative Ontology Alignment Language (EDOAL)
<https://moex.gitlabpages.inria.fr/alignapi/edoal.html>`_ format, which can then be
automatically evaluated by the OAEI's `Alignment API and Alignment Server
<https://moex.gitlabpages.inria.fr/alignapi>`_. A table of past OAEI calls and results
are available below.

During its two-decade runtime, the OAEI consistently reuses the same benchmarks. For
example, the `largebio <https://www.cs.ox.ac.uk/isg/projects/SEALS/oaei/>`_ task for
mapping between the `Foundational Model of Anatomy (FMA)
<https://semantic.farm/registry/fma>`_ ontology, `Systematized Nomenclature of Medicine
- Clinical Terms (SNOMED-CT) <https://semantic.farm/registry/snomedct>`_, and United
States `National Cancer Institute Thesaurus (NCIT)
<https://semantic.farm/registry/ncit>`_ ran between 2011 and 2022 before being
incorporated into the `Bio-ML <https://krr-oxford.github.io/OAEI-Bio-ML/>`_ task, which
still runs as of 2026.

This presents several opportunities to go beyond OAEI, in order to:

1. adopt a better semantic mapping format and software ecosystem
2. store and manually curate the results of mapping prediction
3. maintain old benchmarks and create new ones
4. retire benchmarks for which ontology alignment has been completed

The `Simple Standard for Sharing Ontological Mappings (SSSOM)
<https://mapping-commons.github.io/sssom>`_ and its associated software ecosystem are
still under active maintenance (whereas the alignment API project has not been updated
since 2021), are already considerably better documented than the alignment API and
EDOAL, and adopt much more straightforward languages (Python instead of Java) and
formats (TSV instead of XML).

Community repositories for semantic mappings like `Biomappings
<https://github.com/biopragmatics/biomappings>`_ demonstrated how an `open data, open
code, and open infrastructure (O3) <https://doi.org/10.1038/s41597-024-03406-w>`_
approach democratizes the storage and curation of semantic mappings. The Biomappings
project itself led to the development of the :mod:`sssom_curator` software to wrap
prediction pipelines and provide an interactive curation interface for end users.

The goal of the SSSOM-Pydantic evaluation pipeline is to build on existing tools for
extracting mappings from ontologies (e.g., :mod:`pyobo`), curated resources like
Biomappings, and easily reusable prediction workflows like SSSOM-Curator to
automatically construct new benchmarks based on existing SSSOM documents then
automatically calculate statistics about alignment completion (i.e., how many more
curations are needed to check all predicted mappings, and how many more curations are
needed to complete the alignment?) and the correctness of the prediction software (e.g.,
accuracy, precision, recall, $F_1$).

Until all predictions are curated, the accuracy, precision, recall, and $F_1$ are an
estimation of the true metrics, since the positive and negative manually curated
mappings likely are not complete and therefore have some bias in which things were
curated (e.g., I always curate the easiest first, leading towards a skew that more of my
manual curations result in positive calls).

In the following example, three sources of mappings are combine for the evaluation:

1. Mappings from Medical Action Ontology (MAXO) extracted using :mod:`pyobo`, which
   include mappings to Medical Subject Headings (MeSH) with no metadata, so they default
   to ``oboInOwl:hasDbXref`` as a predicate and ``semapv:UnspecifiedMapping`` as a
   justification.
2. Manually curated mappings from Biomappings, which includes previously curated
   mappings between MAXO and MeSH with high precision predicates and justification.
3. Mappings predicted by the :mod:`sssom_curator` between MAXO and MeSH with lexical
   matching

.. code-block:: console

    \$ pyobo lookup sssom maxo -o maxo.sssom.tsv

    \$ sssom_pydantic subset \
        -i https://w3id.org/biopragmatics/biomappings/sssom/biomappings.sssom.tsv \
        --prefix maxo \
        --target-prefix mesh \
        --no-exclude-negatives \
        --no-exclude-unsure \
        --exclude-predicted \
        -o biomappings-maxo-mesh.sssom.tsv

    \$ mkdir maxo-mesh-predictions
    \$ sssom_curator init --directory maxo-mesh-predictions
    \$ sssom_curator -p maxo-mesh-predictions predict lexical mesh maxo

    \$ sssom_pydantic evaluate \
        -i maxo.sssom.tsv \
        -i biomappings-maxo-mesh.sssom.tsv \
        -i maxo-mesh-predictions/data/predictions.sssom.tsv \
        --accept-unspecified

This workflow pools arbitrary SSSOM files then stratifies them into positive, negative,
predicted (positive), and predicted negative mappings using the :func:`stratify`
function. When extending this workflow to several other OBO Foundry ontologies mapping
to MeSH, a table like this is produced:

======================================== ==================================== ========== ======== ========= ====== =====
Prefix 1                                 Prefix 2                             Completion Accuracy Precision Recall $F_1$
======================================== ==================================== ========== ======== ========= ====== =====
`chebi <https://semantic.farm/chebi>`_   `mesh <https://semantic.farm/mesh>`_ 7.9%       98.2%    98.9%     99.2%  99.1%
`cl <https://semantic.farm/cl>`_         `mesh <https://semantic.farm/mesh>`_ 26.9%      53.4%    90.8%     47.6%  62.5%
`clo <https://semantic.farm/clo>`_       `mesh <https://semantic.farm/mesh>`_ 50.0%      61.9%    66.7%     85.7%  75.0%
`fix <https://semantic.farm/fix>`_       `mesh <https://semantic.farm/mesh>`_ 29.7%      93.5%    93.3%     100.0% 96.6%
`go <https://semantic.farm/go>`_         `mesh <https://semantic.farm/mesh>`_ 32.5%      80.3%    82.6%     96.1%  88.8%
`hgnc <https://semantic.farm/hgnc>`_     `mesh <https://semantic.farm/mesh>`_ 1.9%       43.6%    68.0%     45.9%  54.8%
`hp <https://semantic.farm/hp>`_         `mesh <https://semantic.farm/mesh>`_ 12.2%      96.6%    98.8%     97.7%  98.3%
`maxo <https://semantic.farm/maxo>`_     `mesh <https://semantic.farm/mesh>`_ 43.3%      86.9%    100.0%    86.9%  93.0%
`mi <https://semantic.farm/mi>`_         `mesh <https://semantic.farm/mesh>`_ 17.6%      95.8%    95.8%     100.0% 97.9%
`mmo <https://semantic.farm/mmo>`_       `mesh <https://semantic.farm/mesh>`_ 39.6%      88.9%    100.0%    88.9%  94.1%
`ms <https://semantic.farm/ms>`_         `mesh <https://semantic.farm/mesh>`_ 44.8%      81.5%    80.8%     100.0% 89.4%
`so <https://semantic.farm/so>`_         `mesh <https://semantic.farm/mesh>`_ 14.6%      95.2%    95.2%     100.0% 97.6%
`txpo <https://semantic.farm/txpo>`_     `mesh <https://semantic.farm/mesh>`_ 25.8%      72.6%    98.4%     73.5%  84.1%
`uberon <https://semantic.farm/uberon>`_ `mesh <https://semantic.farm/mesh>`_ 7.1%       12.2%    98.7%     12.2%  21.7%
`vo <https://semantic.farm/vo>`_         `mesh <https://semantic.farm/mesh>`_ 69.4%      64.1%    91.2%     53.8%  67.6%
`vto <https://semantic.farm/vto>`_       `mesh <https://semantic.farm/mesh>`_ 0.3%       50.0%    50.0%     100.0% 66.7%
`xlmod <https://semantic.farm/xlmod>`_   `mesh <https://semantic.farm/mesh>`_ 44.7%      98.7%    98.7%     100.0% 99.3%
======================================== ==================================== ========== ======== ========= ====== =====

Note that lexical matching typically has a high precision (i.e., most predictions are
right) but lower recall (i.e., some potential predictions are missed). Given the problem
domain that (almost all) ontologies don't have one-to-many or many-to-one mappings, then
it's also possible to identify entities for which there is no mapping between two given
resources and further increase the accuracy of the accuracy metric.

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

from ..api import SemanticMapping
from ..constants import PREDICTION_PREDICATES

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

    #: Completion is the ratio of curated / (curated + predicted),
    #: where closer to 1.0 means that more of the curation has been done
    completion: float

    accuracy: float
    precision: float
    recall: float
    f1: float


def evaluate_predictions(
    mappings: Iterable[SemanticMapping],
    *,
    accept_unspecified: bool = True,
    _tag: str | None = None,
) -> dict[UnorderedPrefixPair, Evaluation]:
    """Stratify and evaluate predicted mappings against curated mappings.

    :param mappings: A pool of positive, negative, and predicted semantic mappings
        :param accept_unspecified: Whether to consider mappings that do not have an
        explicit justification (i.e., using ``semapv:UnspecifiedMatching``) as having
        been manually curated. See :func:`stratify` for more details.

    :returns: A mapping from unordered prefix pairs to evaluation objects
    """
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
                tag=_tag,
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


def tabulate_evaluation(
    res: dict[UnorderedPrefixPair, Evaluation], tablefmt: str | None = None
) -> str:
    """Tabulate the evaluation results."""
    from tabulate import tabulate

    rows = []
    for unordered_prefix_pair, evaluation in res.items():
        prefix_1, prefix_2 = sorted(unordered_prefix_pair)
        rows.append((prefix_1, prefix_2, *evaluation))
    return tabulate(
        rows,
        headers=["Prefix 1", "Prefix 2", "Completion", "Accuracy", "Precision", "Recall", "F1"],
        floatfmt=".1%",
        tablefmt=tablefmt or "github",
    )
