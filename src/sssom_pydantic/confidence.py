"""Defines a confidence model."""

import math
import statistics
from collections.abc import Iterable
from typing import Literal, TypeAlias

from sssom_pydantic import SemanticMapping

__all__ = ["get_mapping_confidence"]

ConfidenceModel: TypeAlias = Literal["binomial", "mean"]


def get_mapping_confidence(
    mappings: Iterable[SemanticMapping], confidence_model: ConfidenceModel = "mean"
) -> float:
    """Get a confidence score for the mapping."""
    if _not_all_same_triple(mappings):
        raise ValueError
    creator_confidences = []
    reviewer_agreements = []
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
        if mapping.reviewers is not None:
            if mapping.reviewer_agreement:
                if mapping.negated:
                    reviewer_agreements.append(1.0 - mapping.reviewer_agreement)
                else:
                    reviewer_agreements.append(mapping.reviewer_agreement)
            else:
                if mapping.negated:
                    reviewer_agreements.append(-1.0)
                else:
                    reviewer_agreements.append(1.0)
    return _aggregate_confidences(
        creator_confidences, reviewer_agreements, confidence_model=confidence_model
    )


def _aggregate_confidences(
    creator_confidences: list[float],
    reviewer_agreements: list[float],
    confidence_model: ConfidenceModel = "mean",
) -> float:
    match confidence_model:
        case "mean":
            c = statistics.mean(creator_confidences)
        case "binomial":
            c = 1.0 - math.prod(1.0 - x for x in creator_confidences)
        case _:
            raise ValueError

    if not reviewer_agreements:
        return c

    direction = statistics.mean(reviewer_agreements)  # R
    strength = statistics.mean(abs(a) for a in reviewer_agreements)  # W
    rv = (1 - strength) * c + strength * (1 + direction) / 2
    return rv


def _not_all_same_triple(mappings: Iterable[SemanticMapping]) -> bool:
    return len({(m.subject, m.predicate, m.object) for m in mappings}) > 1


def plot2d() -> None:
    """Plot the confidence model in 2D."""
    import matplotlib.pyplot as plt
    import numpy as np

    creator_linspace = np.linspace(0, 1, 100)
    reviewer_linspace = np.linspace(-1, 1, 100)

    reviewer, creator = np.meshgrid(reviewer_linspace, creator_linspace)

    z = np.array(
        [
            _aggregate_confidences([c], [r])
            for c, r in zip(creator.reshape(-1), reviewer.reshape(-1), strict=False)
        ]
    ).reshape((100, 100))

    fig, ax = plt.subplots()
    mesh = ax.pcolormesh(creator, reviewer, z, cmap="RdBu")
    ax.set_xlabel("Creator Confidence")
    ax.set_ylabel("Reviewer Agreement")
    ax.set_title("Aggregation of Creator Confidence\nand Reviewer Agreement")
    ax.axis([0, 1, -1, 1])
    fig.colorbar(mesh, ax=ax)
    plt.show()
    plt.savefig("images/reviewer-agreement-aggregation.svg")


if __name__ == "__main__":
    plot2d()
