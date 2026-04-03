"""Defines a confidence model."""

import math
import statistics
from collections.abc import Iterable
from typing import Literal, TypeAlias

from .api import SemanticMapping

__all__ = [
    "estimate_confidence",
    "ConfidenceModel",
]

ConfidenceModel: TypeAlias = Literal["binomial", "mean"]


def estimate_confidence(
    mappings: Iterable[SemanticMapping],
    *,
    confidence_model: ConfidenceModel | None = None,
    check: bool = True,
) -> float:
    """Estimate the confidence for multiple mappings."""
    if check and _not_all_same_triple(mappings):
        raise ValueError
    creator_confidences = []
    for mapping in mappings:
        if mapping.confidence is not None:
            if mapping.negated:
                creator_confidences.append(1.0 - mapping.confidence)
            else:
                creator_confidences.append(mapping.confidence)
        else:
            if mapping.negated:
                creator_confidences.append(0.0)
            else:
                creator_confidences.append(1.0)

    return _aggregate_confidences(
        creator_confidences, confidence_model=confidence_model
    )


def _aggregate_confidences(
    creator_confidences: list[float],
    *,
    confidence_model: ConfidenceModel | None = None,
) -> float:
    match confidence_model:
        case "mean" | None:
            c = statistics.mean(creator_confidences)
        case "binomial":
            c = 1.0 - math.prod(1.0 - x for x in creator_confidences)
        case _:
            raise ValueError

    return c


def _not_all_same_triple(mappings: Iterable[SemanticMapping]) -> bool:
    return len({(m.subject, m.predicate, m.object) for m in mappings}) > 1
