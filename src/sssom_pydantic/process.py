"""Utilities for working with semantic mappings."""

from __future__ import annotations

import datetime
import itertools as itt
import math
import statistics
import typing
from collections import defaultdict
from collections.abc import Callable, Collection, Iterable
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    TypeAlias,
    TypeVar,
    cast,
    get_args,
)

from curies import Reference
from curies.vocabulary import (
    SemanticMappingScope,
    manual_mapping_curation,
    semantic_mapping_scopes,
)

from . import RequiredSemanticMapping, SemanticMapping

if TYPE_CHECKING:
    from _typeshed import SupportsRichComparison

__all__ = [
    "MARKS",
    "MARK_TO_CALL",
    "Call",
    "CanonicalMappingTuple",
    "ConfidenceModel",
    "ExistsAction",
    "Hasher",
    "InvalidExistsActionError",
    "Mark",
    "curate",
    "estimate_confidence",
    "get_canonical_tuple",
    "publish",
    "remove_redundant_external",
    "remove_redundant_internal",
    "review",
]

#: A canonical mapping tuple
CanonicalMappingTuple: TypeAlias = tuple[str, str, str, str]

#: A type variable bound to a semantic mapping type, to
#: make it possible to annotate functions that spit out the
#: same type that goes in
MappingTypeVar = TypeVar("MappingTypeVar", bound=RequiredSemanticMapping)

#: The type used in hashing functions.
HashTarget = TypeVar("HashTarget")

#: A function that constructs a hashable object from a semantic mapping
Hasher: TypeAlias = Callable[[MappingTypeVar], HashTarget]

#: A function that makes a comparable score for a semantic mapping
Scorer: TypeAlias = Callable[[MappingTypeVar], "SupportsRichComparison"]

#: A decision about a specific curation
Call: TypeAlias = Literal["correct", "incorrect", "unsure"]

#: A decision or an overwrite for a specific curation
Mark: TypeAlias = Call | SemanticMappingScope

#: A set of all possible marks.
MARKS: set[Mark] = set(get_args(Call)).union(get_args(SemanticMappingScope))

#: Mapping from marks to calls
MARK_TO_CALL: dict[Mark, Call] = {
    "correct": "correct",
    "incorrect": "incorrect",
    "unsure": "unsure",
    "BROAD": "correct",
    "NARROW": "correct",
    "CLOSE": "correct",
    "RELATED": "correct",
}


def remove_redundant_internal(
    mappings: Iterable[MappingTypeVar],
    *,
    key: Hasher[MappingTypeVar, HashTarget] | None = None,
    scorer: Scorer[MappingTypeVar] | None = None,
) -> list[MappingTypeVar]:
    """Remove redundant mappings.

    :param mappings: An iterable of mappings
    :param key: A function that hashes the mappings. If not given, will only use the
        subject/object to has the mapping.
    :param scorer: A function that gives a score to a given mapping, where a higher
        score means it's more likely to be kept. Any function returning a comparable
        value can be used, but int/float are the easiest to understand.

    :returns: A list of mappings that have had duplicates dropped. This does not
        necessarily maintain order, since dictionary-based aggregation happens in the
        implementation.
    """
    if key is None:
        key = cast(Hasher[MappingTypeVar, HashTarget], get_canonical_tuple)

    if scorer is None:
        scorer = _score_mapping

    key_to_mappings: defaultdict[HashTarget, list[MappingTypeVar]] = defaultdict(list)
    for mapping in mappings:
        key_to_mappings[key(mapping)].append(mapping)
    return [max(mappings, key=scorer) for mappings in key_to_mappings.values()]


def _score_mapping(mapping: RequiredSemanticMapping) -> int:
    """Assign a value for this mapping, where higher is better.

    :param mapping: A mapping dictionary

    :returns: An integer, where higher means a better choice.

    This function is currently simple, but can later be extended to account for several
    other things including:

    - confidence in the curator
    - prediction methodology
    - date of prediction/curation (to keep the earliest)
    """
    author: Reference | None = getattr(mapping, "author", None)
    if author and author.prefix == "orcid":
        return 1
    return 0


def get_canonical_tuple(mapping: RequiredSemanticMapping) -> CanonicalMappingTuple:
    """Get the canonical tuple from a mapping entry."""
    source, target = sorted([mapping.subject, mapping.object])
    return source.prefix, source.identifier, target.prefix, target.identifier


def remove_redundant_external(
    mappings: Iterable[MappingTypeVar],
    *others: Iterable[MappingTypeVar],
    key: Hasher[MappingTypeVar, HashTarget] | None = None,
) -> list[MappingTypeVar]:
    """Remove mappings with same S/O pairs in other given mappings."""
    keep_mapping_predicate: Callable[[MappingTypeVar], bool] = _get_predicate_helper(
        *others, key=key
    )
    return [m for m in mappings if keep_mapping_predicate(m)]


def _get_predicate_helper(
    *mappings: Iterable[MappingTypeVar],
    key: Hasher[MappingTypeVar, HashTarget] | None = None,
) -> Callable[[MappingTypeVar], bool]:
    """Construct a predicate for mapping membership.

    :param mappings: A variadic number of mapping lists, which are all indexed
    :param key: A function that hashes a given semantic mapping. If not given, one that
        uses the combination of subject + object will be used.

    :returns: A predicate that can be used to check if new mappings are already in the
        given mapping list(s)
    """
    if key is None:
        key = cast(Hasher[MappingTypeVar, HashTarget], get_canonical_tuple)

    skip_tuples: set[HashTarget] = {key(mapping) for mapping in itt.chain.from_iterable(mappings)}

    def _keep_mapping(mapping: MappingTypeVar) -> bool:
        return key(mapping) not in skip_tuples

    return _keep_mapping


ExistsAction: TypeAlias = Literal["error", "overwrite", "keep"]


class InvalidExistsActionError(ValueError):
    """An error for an invalid exists action."""

    def __init__(self, value: str) -> None:
        """Initialize the exception."""
        self.value = value

    def __str__(self) -> str:
        return f"invalid exists_action: {self.value}. Use one of {typing.get_args(ExistsAction)}"


def curate(
    mapping: SemanticMapping,
    /,
    authors: Reference | list[Reference],
    mark: Mark,
    confidence: float | None = None,
    add_date: bool = True,
    **kwargs: Any,
) -> SemanticMapping:
    """Curate a mapping."""
    if mapping.justification == manual_mapping_curation:
        raise ValueError("should use review workflow on previously manually curated mappings")

    if mark == "unsure":
        return review(mapping, reviewers=authors, score=0)

    if isinstance(authors, Reference):
        authors = [authors]

    update = {
        "justification": manual_mapping_curation,
        "authors": authors,
        "confidence": confidence,
        # Zero out the following
        "mapping_tool": None,
        "similarity_measure": None,
        "similarity_score": None,
        **kwargs,
    }

    # Add a flag for maintaining backwards compatibility
    # with workflows that don't track this
    if add_date:
        update["mapping_date"] = datetime.date.today()

    if mark in semantic_mapping_scopes:
        update["predicate"] = semantic_mapping_scopes[mark]
    elif mark == "incorrect":
        update["predicate_modifier"] = "Not"
    elif mark == "correct":
        pass  # nothing needed here!
    else:
        raise ValueError(f"invalid mark: {mark}")

    new_mapping = mapping.model_copy(update=update)
    return new_mapping


def review(
    mapping: SemanticMapping,
    reviewers: Reference | list[Reference],
    *,
    score: float | None = None,
    date: datetime.date | None = None,
    exists_action: ExistsAction | None = None,
) -> SemanticMapping:
    """Review a mapping and produce a new record.

    :param mapping: A semantic mapping record
    :param reviewers: A reviewer or list of reviewers
    :param score: The agreement score, where 1.0 means agree, 0.0 means unsure, and -1.0
        means disagree
    :param date: The date of the review. Defaults to today.
    :param exists_action: The action to take if a reviewer already exists. By default,
        will raise a value error.

    :returns: A new mapping record with new reviewer information. If there was already
        reviewer information, this will get overwritten.

    :raises ValueError: If the mapping already has reviewer information, and
        ``exists_action`` is either set to "error" or is unset (since error is the
        default action)
    :raises InvalidExistsActionError: if an invalid value is passed to ``exists_action``
    """
    if score is None:
        score = 1.0
    elif score < -1.0:
        raise ValueError(
            f"reviewer agreement score should be from [-1.0, 1.0], got too low {score}"
        )
    elif score > 1.0:
        raise ValueError(
            f"reviewer agreement score should be from [-1.0, 1.0], got too high {score}"
        )
    if date is None:
        date = datetime.date.today()
    if mapping.reviewers:
        if exists_action == "error" or exists_action is None:
            raise ValueError("trying to overwrite existing reviewers")
        elif exists_action == "keep":
            return mapping
        elif exists_action == "overwrite":
            pass  # just use the implementation below to update the publication date
        else:
            raise InvalidExistsActionError(exists_action)
    if isinstance(reviewers, Reference):
        reviewers = [reviewers]
    update = {
        "reviewers": reviewers,
        "review_date": date,
        "reviewer_agreement": score,
    }
    return mapping.model_copy(update=update)


def publish(
    mapping: SemanticMapping,
    /,
    *,
    exists_action: ExistsAction | None = None,
    date: datetime.date | None = None,
) -> SemanticMapping:
    """Add a publication date to the mapping."""
    if mapping.publication_date is not None:
        if exists_action == "error" or exists_action is None:
            raise ValueError
        elif exists_action == "keep":
            return mapping
        elif exists_action == "overwrite":
            pass  # just use the implementation below to update the publication date
        else:
            raise InvalidExistsActionError(exists_action)
    rv = mapping.model_copy(
        update={"publication_date": date if date is not None else datetime.date.today()}
    )
    return rv


#: Models for aggregating mapping confidences
ConfidenceModel: TypeAlias = Literal["binomial", "mean"]


def estimate_confidence(
    mappings: Collection[SemanticMapping],
    *,
    confidence_model: ConfidenceModel | None = None,
    check: bool = True,
) -> float:
    r"""Estimate the confidence of a subject-predicate-triple based on multiple evidences.

    :param mappings: A collection of mappings that all have the same
        subject-predicate-object triple. This algorithm explicitly handles when there is
        a negative predicate modifier.
    :param confidence_model: Which confidence model to use when aggregating mapping
        confidences.

        - mean aggregation is $\frac{1}{n} \sum_{i=1}^n c_i$
        - binomial aggregation is $1 - \prod_{i=1}^n (1 - c_i)$
    :param check: Should mappings be checked to all have the same
        subject-predicate-object triple? This can be disabled if you're sure they
        already match

    :returns: A single floating point confidence estimate of the positive
        subject-predicate-object triple, where 1.0 is highly confident and 0.0 is not
        confident. To get the confidence for the negated subject-predicate-object
        triple, subtract this return value from 1.0.

    .. note::

        We define the confidence in an empty list to be 1.0
    """
    if check and _not_all_same_triple(mappings):
        raise ValueError

    if not mappings:
        return 1.0

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
    *,
    confidence_model: ConfidenceModel | None = None,
) -> float:
    match confidence_model:
        case "mean" | None:
            c = statistics.mean(creator_confidences)
        case "binomial":
            c = 1.0 - math.prod(1.0 - x for x in creator_confidences)
        case _:
            raise ValueError(
                f"unknown confidence model. use one of {typing.get_args(ConfidenceModel)}"
            )

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
