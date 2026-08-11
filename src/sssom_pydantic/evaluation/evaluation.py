"""A workflow for evaluating predicted mappings."""

from collections import defaultdict
from collections.abc import Iterable
from typing import NamedTuple, TypeAlias, TypeVar

import curies
from curies import Reference
from curies import vocabulary as v
from tqdm import tqdm

from sssom_pydantic import SemanticMapping

X = TypeVar("X")


def _get_v1(
    positive_set: set[X], negative_set: set[X], predicted_set: set[X]
) -> tuple[int, int, int, int]:
    tp = len(positive_set.intersection(predicted_set))  # true positives
    fn = len(positive_set - predicted_set)  # false negatives
    fp = len(negative_set.intersection(predicted_set))  # false positives
    tn = len(negative_set - predicted_set)  # true negatives
    return tp, fp, fn, tn


UnorderedPrefixPair: TypeAlias = frozenset[str]

DD: TypeAlias = dict[UnorderedPrefixPair, set[str]]

PREDICTION_PREDICATES = {
    v.lexical_matching_process,
    v.lexical_similarity_threshold_based_matching_process,
    v.logical_reasoning_matching_process,
    v.semantic_similarity,
    v.structural_matching,
}


def stratify(mappings: Iterable[SemanticMapping], converter: curies.Converter) -> tuple[DD, DD, DD]:
    """Stratify a set of mappings."""
    positive: defaultdict[UnorderedPrefixPair, set[str]] = defaultdict(set)
    negative: defaultdict[UnorderedPrefixPair, set[str]] = defaultdict(set)
    predicted: defaultdict[UnorderedPrefixPair, set[str]] = defaultdict(set)
    unhandled_justifications: set[Reference] = set()

    # TODO should predicate be accounted for, or should this workflow
    #  just assume squashing has been done correctly first?
    # TODO use broad match and exact match to infer NOT exact match?
    # TODO squash higher relations into exact match?
    for m in mappings:
        # todo could also use hash triple
        xx = f"{m.subject.curie}-{m.object.curie}"
        prefix_pair: UnorderedPrefixPair = frozenset([m.subject.prefix, m.object.prefix])
        if m.justification in PREDICTION_PREDICATES:
            # assume there are no negative predictions
            predicted[prefix_pair].add(xx)
        elif m.justification == v.manual_mapping_curation:
            if m.predicate_modifier is None:
                positive[prefix_pair].add(xx)
            else:
                negative[prefix_pair].add(xx)
        elif m.justification not in unhandled_justifications:
            unhandled_justifications.add(m.justification)
            tqdm.write(f"unhandled mapping justification: {m.justification.curie}")
    return dict(positive), dict(negative), dict(predicted)


class Evaluation(NamedTuple):
    """An evaluation tuple."""

    completion: float
    accuracy: float
    precision: float
    recall: float
    f1: float


def evaluate_predictions(
    mappings: Iterable[SemanticMapping],
    converter: curies.Converter,
    *,
    tag: str | None = None,
) -> dict[UnorderedPrefixPair, Evaluation]:
    """Evaluate predicted mappings using manually curated positive and negative mappings."""
    positive_set, negative_set, predicted_set = stratify(mappings, converter)
    keys = set(positive_set).union(negative_set).union(predicted_set)
    rv = {}
    for key in keys:
        rv[key] = _evaluate_helper(
            positive_set[key], negative_set[key], predicted_set[key], tag=tag
        )
    return rv


def _evaluate_helper(
    positive_set: set[str],
    negative_set: set[str],
    predicted_set: set[str],
    *,
    tag: str | None = None,
) -> Evaluation:
    tp, fp, fn, tn = _get_v1(positive_set, negative_set, predicted_set)

    predicted_only = len(predicted_set - positive_set - negative_set)
    union_len = len(positive_set.union(predicted_set).union(negative_set))

    msg = f"union={union_len:,}, intersection={tp:,}, curated={fn:,}, predicted={predicted_only:,}"
    if tag is not None:
        msg = f"[{tag}] {msg}"
    tqdm.write(msg)

    accuracy = (tp + tn) / (tp + tn + fp + fn)
    recall = tp / (tp + fn)
    precision = tp / (tp + fp)
    f1 = 2 * tp / (2 * tp + fp + fn)
    completion = 1 - predicted_only / len(predicted_set)

    # what is the percentage of curated examples that are positive?
    _positive_percentage = len(positive_set) / (len(positive_set) + len(negative_set))

    return Evaluation(completion, accuracy, precision, recall, f1)
