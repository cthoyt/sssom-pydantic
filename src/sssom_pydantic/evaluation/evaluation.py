"""A workflow for evaluating predicted mappings."""

import logging
from collections import defaultdict
from collections.abc import Iterable
from typing import NamedTuple, TypeAlias, TypeVar

import curies
from curies.vocabulary import lexical_matching_process, manual_mapping_curation

from sssom_pydantic import SemanticMapping

logger = logging.getLogger(__name__)

X = TypeVar("X")


def _get_v1(
    positive_set: set[X], negative_set: set[X], predicted_set: set[X]
) -> tuple[int, int, int, int]:
    tp = len(positive_set.intersection(predicted_set))  # true positives
    fp = len(negative_set.intersection(predicted_set))  # false positives
    fn = len(positive_set - predicted_set)  # false negatives
    tn = len(negative_set - predicted_set)  # true negatives
    return tp, fp, fn, tn


DD: TypeAlias = dict[str, set[SemanticMapping]]


def stratify(mappings: Iterable[SemanticMapping], converter: curies.Converter) -> tuple[DD, DD, DD]:
    """Stratify a set of mappings."""
    positive, negative, predicted = defaultdict(set), defaultdict(set), defaultdict(set)
    for mapping in mappings:
        hsh = converter.hash_triple(mapping)
        if mapping.justification == lexical_matching_process:
            predicted[hsh].add(mapping)
        elif (
            mapping.justification == manual_mapping_curation and mapping.predicate_modifier is None
        ):
            positive[hsh].add(mapping)
        elif (
            mapping.justification == lexical_matching_process
            and mapping.predicate_modifier is not None
        ):
            negative[hsh].add(mapping)
        else:
            pass  # TODO what to do with others?
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
) -> Evaluation:
    """Evaluate predicted mappings using ground truth positive and negative mappings."""
    positive_set, negative_set, predicted_set = map(set, stratify(mappings, converter))

    tp, fp, fn, tn = _get_v1(positive_set, negative_set, predicted_set)

    predicted_only = len(predicted_set - positive_set - negative_set)
    union_len = len(positive_set.union(predicted_set).union(negative_set))

    msg = f"union={union_len:,}, intersection={tp:,}, curated={fn:,}, predicted={predicted_only:,}"
    if tag is not None:
        msg = f"[{tag}] {msg}"
    logger.info(msg)

    accuracy = (tp + tn) / (tp + tn + fp + fn)
    recall = tp / (tp + fn)
    precision = tp / (tp + fp)
    f1 = 2 * tp / (2 * tp + fp + fn)
    completion = 1 - predicted_only / len(predicted_set)

    # what is the percentage of curated examples that are positive?
    _positive_percentage = len(positive_set) / (len(positive_set) + len(negative_set))

    return Evaluation(completion, accuracy, precision, recall, f1)
