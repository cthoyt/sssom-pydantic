"""Utilities for working with semantic mappings."""

from __future__ import annotations

import datetime
import enum
import itertools as itt
import math
import statistics
import typing
from collections import defaultdict
from collections.abc import Callable, Collection, Iterable
from typing import TYPE_CHECKING, Any, Literal, TypeAlias, cast, get_args

import curies
from curies import Converter, Reference
from curies.vocabulary import (
    SemanticMappingScope,
    broad_match,
    manual_mapping_curation,
    mapping_inversion,
    narrow_match,
    semantic_mapping_inversions,
    semantic_mapping_scopes,
)
from typing_extensions import TypeVar

from .api import MappingTypeVar, SemanticMapping, SemanticMappingPredicate, hash_triple_to_reference

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
    "exclude_negative",
    "exclude_unsure",
    "filter_by_confidence",
    "get_canonical_tuple",
    "invert",
    "invert_broad_matches",
    "invert_by_object_prefix",
    "invert_by_prefix_pair",
    "invert_by_subject_prefix",
    "invert_narrow_matches",
    "merge_manual_curations",
    "publish",
    "remove_redundant_external",
    "remove_redundant_internal",
    "review",
]

#: A canonical mapping tuple
CanonicalMappingTuple: TypeAlias = tuple[str, str, str, str]

#: The type used in hashing functions, which get put into a set.
#: This is set with ``tuple[str, ...]`` as a default because normally,
#: The hash function used is :func:`get_canonical_tuple`
HashTarget = TypeVar("HashTarget", bound=typing.Hashable, default=tuple[str, ...])

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


def _score_mapping(mapping: SemanticMapping) -> int:
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


def get_canonical_tuple(mapping: SemanticMapping) -> CanonicalMappingTuple:
    """Get the canonical tuple from a mapping entry."""
    subject, object_ = sorted([mapping.subject, mapping.object])
    return subject.prefix, subject.identifier, object_.prefix, object_.identifier


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
    date: datetime.date | None = None,
    add_date: bool = True,
    **kwargs: Any,
) -> SemanticMapping:
    """Curate a mapping."""
    if mapping.justification == manual_mapping_curation:
        raise ValueError("should use review workflow on previously manually curated mappings")

    if mark == "unsure":
        return review(mapping, reviewers=authors, date=date, score=0.0)

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

    # if this mapping was previously reviewed as
    # unsure, clear it
    if mapping.reviewer_agreement == 0.0:
        update["reviewers"] = None
        update["reviewer_agreement"] = None
        update["review_date"] = None

    # Add a flag for maintaining backwards compatibility
    # with workflows that don't track this
    if add_date:
        if date is None:
            date = datetime.date.today()
        update["mapping_date"] = date

    if mark in semantic_mapping_scopes:
        update["predicate"] = semantic_mapping_scopes[mark].without_name()
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


#: A set of the stems of field names that
#: should be swapped during inversion
_EXCHANGEABLE_FIELDS: set[str] = set()
for key in SemanticMapping.model_fields:
    if key.startswith("subject_"):
        _EXCHANGEABLE_FIELDS.add(key[len("subject_") :])
    elif key.startswith("object_"):
        _EXCHANGEABLE_FIELDS.add(key[len("object_") :])


class InversionJustificationPolicy(enum.Enum):
    """An enumeration of different inversion derivation policies."""

    #: Keep the original justification (default)
    retain = enum.auto()

    #: Derive a new evidence, whose justification is ``semapv:MappingInversion``
    derive = enum.auto()

    @classmethod
    def parse(
        cls, value: InversionJustificationPolicy | str | None
    ) -> InversionJustificationPolicy:
        """Parse an inversion derivation policy."""
        match value:
            case None | "retain":
                return cls.retain
            case "derive":
                return cls.derive
            case InversionJustificationPolicy():
                return value
        raise ValueError(f"invalid inversion derivation: {value}")


def invert(
    mapping: MappingTypeVar,
    *,
    converter: Converter,
    justification_policy: InversionJustificationPolicy | None = None,
) -> MappingTypeVar:
    """Invert a mapping.

    :param mapping: A semantic mapping record
    :param converter: A converter function hashing the mapping to fill the
        "derives_from" field
    :param justification_policy: The policy for how the original evidence is mutated
        during inversion. Defaults to :class:`InversionDerivationPolicy.retain`, where
        the original justification is retained

    :returns: An inverted mapping. Mapping inversion clears the ``record`` field if
        present.

    >>> from curies import NamableReference, Converter
    >>> from curies.vocabulary import charlie, manual_mapping_curation, exact_match
    >>> from sssom_pydantic import SemanticMapping, hash_triple_to_reference
    >>> converter = Converter.from_prefix_map(
    ...     {
    ...         "CHEBI": "http://purl.obolibrary.org/obo/CHEBI_",
    ...         "mesh": "http://id.nlm.nih.gov/mesh/",
    ...         "skos": "http://www.w3.org/2004/02/skos/core#",
    ...         "semapv": "https://w3id.org/semapv/vocab/",
    ...     }
    ... )
    >>> mapping = SemanticMapping(
    ...     subject=NamableReference(prefix="mesh", identifier="C000089", name="ammeline"),
    ...     predicate=exact_match,
    ...     object=NamableReference(prefix="CHEBI", identifier="28646", name="ammeline"),
    ...     justification=manual_mapping_curation,
    ...     authors=[charlie],
    ...     mapping_date="2026-04-21",
    ... )
    >>> hash_triple_to_reference(mapping, converter)
    Reference(prefix='mapping', identifier='36a1f9244ea7641a90987c82f33c25c0c13712ee8f48207b2a0825f8a4e4e26a')
    >>> mapping_inv = invert(mapping, converter=converter)
    >>> mapping_inv.subject
    NamableReference(prefix='CHEBI', identifier='28646', name='ammeline')
    >>> mapping_inv.object
    NamableReference(prefix='mesh', identifier='C000089', name='ammeline')
    >>> mapping_inv.derived_from
    [Reference(prefix='mapping', identifier='36a1f9244ea7641a90987c82f33c25c0c13712ee8f48207b2a0825f8a4e4e26a')]
    """  # noqa:E501
    new_predicate: curies.Reference | None = semantic_mapping_inversions.get(mapping.predicate)
    if new_predicate is None:
        raise NotImplementedError(
            f"inversion is not implemented for predicate: {mapping.predicate}"
        )
    if mapping.justification == mapping_inversion:
        raise ValueError("double inversion is not supported")

    if not mapping.predicate.name:
        new_predicate = new_predicate.without_name()

    update: dict[str, Any] = {
        "subject": mapping.object,
        "predicate": new_predicate,
        "object": mapping.subject,
        "record": None,  # need to clear the record, since the mapping will now have a new identity
        # TODO update cardinality?
    }

    if justification_policy is InversionJustificationPolicy.derive:
        update["justification"] = mapping_inversion
        update["derived_from"] = [hash_triple_to_reference(mapping, converter)]

    for part in _EXCHANGEABLE_FIELDS:
        subject_part = getattr(mapping, f"subject_{part}")
        object_part = getattr(mapping, f"object_{part}")
        if subject_part and object_part:
            update[f"object_{part}"] = subject_part
            update[f"subject_{part}"] = object_part
        elif subject_part:
            update[f"object_{part}"] = subject_part
            update[f"subject_{part}"] = None
        else:  # elif object_part
            update[f"object_{part}"] = None
            update[f"subject_{part}"] = object_part

    return mapping.model_copy(update=update)


#: Models for aggregating mapping confidences
ConfidenceModel: TypeAlias = Literal["binomial", "mean"]


def estimate_confidence(
    mappings: Collection[SemanticMapping],
    *,
    confidence_model: ConfidenceModel | None = None,
    check: bool = True,
    precision: int | None = None,
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
        creator_confidences,
        reviewer_agreements,
        confidence_model=confidence_model,
        precision=precision,
    )


def _aggregate_confidences(
    creator_confidences: list[float],
    reviewer_agreements: list[float],
    *,
    confidence_model: ConfidenceModel | None = None,
    precision: int | None = None,
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
        if precision:
            c = round(c, precision)
        return c

    direction = statistics.mean(reviewer_agreements)  # R
    strength = statistics.mean(abs(a) for a in reviewer_agreements)  # W
    rv = (1 - strength) * c + strength * (1 + direction) / 2
    if precision:
        rv = round(rv, precision)
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


def exclude_negative(mappings: Iterable[MappingTypeVar]) -> Iterable[MappingTypeVar]:
    """Exclude negative mappings.

    :param mappings: An iterable of semantic mappings

    :returns: A list of semantic mappings, with all negative mappings excluded

    >>> from sssom_pydantic import SemanticMapping, NOT
    >>> m1 = SemanticMapping.exact("mesh:C000089", "CHEBI:28646")
    >>> m2 = SemanticMapping.exact("mesh:C000089", "CHEBI:28647", predicate_modifier=NOT)
    >>> assert [m1] == list(exclude_negative([m1, m2]))
    """
    for mapping in mappings:
        if mapping.predicate_modifier is None:
            yield mapping


def exclude_unsure(mappings: Iterable[MappingTypeVar]) -> Iterable[MappingTypeVar]:
    """Exclude usunre mappings.

    :param mappings: An iterable of semantic mappings

    :returns: A list of semantic mappings, with all unsure mappings excluded. Mappings
        are considered unsure when there's a explicit reviewer agreement of 0.0.

    >>> from sssom_pydantic import SemanticMapping, NOT
    >>> m1 = SemanticMapping.exact("CHEBI:48552", "MESH:D020926")
    >>> m2 = SemanticMapping.exact("CHEBI:53227", "MESH:D020959", reviewer_agreement=1.0)
    >>> m3 = SemanticMapping.exact("CHEBI:82761", "MESH:D023082", reviewer_agreement=0.0)
    >>> assert [m1, m2] == list(exclude_unsure([m1, m2, m3]))
    """
    for mapping in mappings:
        if mapping.reviewer_agreement != 0.0:
            yield mapping


def invert_by_predicate(
    mappings: Iterable[MappingTypeVar],
    predicate: SemanticMappingPredicate,
    *,
    converter: curies.Converter,
    justification_policy: InversionJustificationPolicy | str | None = None,
) -> Iterable[MappingTypeVar]:
    """Invert based on prefixes.

    :param mappings: An iterable of semantic mappings
    :param predicate: A predicate function
    :param converter: A converter function hashing the mapping to fill the
        "derives_from" field
    :param justification_policy: The policy for how the original evidence is mutated
        during inversion. Defaults to :class:`InversionDerivationPolicy.retain`, where
        the original justification is retained

    :returns: An iterable of semantic mappings, with the correct ones inverted

    .. note::

        mappings with ``semapv:MappingInversion`` justification are simply yielded and
        not considered for re-inverting
    """
    justification_policy = InversionJustificationPolicy.parse(justification_policy)
    for mapping in mappings:
        if (
            mapping.justification != mapping_inversion
            and mapping.predicate in semantic_mapping_inversions
            and predicate(mapping)
        ):
            yield invert(mapping, converter=converter, justification_policy=justification_policy)
        else:
            yield mapping


def invert_narrow_matches(
    mappings: Iterable[MappingTypeVar],
    *,
    converter: curies.Converter,
    justification_policy: InversionJustificationPolicy | str | None = None,
) -> Iterable[MappingTypeVar]:
    """Invert narrow matches into broad matches.

    :param mappings: An iterable of semantic mappings
    :param converter: A converter function hashing the mapping to fill the
        "derives_from" field
    :param justification_policy: The policy for how the original evidence is mutated
        during inversion. Defaults to :class:`InversionDerivationPolicy.retain`, where
        the original justification is retained

    :returns: An iterable of semantic mappings, with the narrow matches inverted into
        broad ones

    This is useful when creating OWL bridging axioms.
    """
    yield from _invert_by_mapping_predicate(
        mappings, narrow_match, converter=converter, justification_policy=justification_policy
    )


def invert_broad_matches(
    mappings: Iterable[MappingTypeVar],
    *,
    converter: curies.Converter,
    justification_policy: InversionJustificationPolicy | str | None = None,
) -> Iterable[MappingTypeVar]:
    """Invert broad matches into narrow matches.

    :param mappings: An iterable of semantic mappings
    :param converter: A converter function hashing the mapping to fill the
        "derives_from" field
    :param justification_policy: The policy for how the original evidence is mutated
        during inversion. Defaults to :class:`InversionDerivationPolicy.retain`, where
        the original justification is retained

    :returns: An iterable of semantic mappings, with the narrow matches inverted into
        broad ones
    """
    yield from _invert_by_mapping_predicate(
        mappings, broad_match, converter=converter, justification_policy=justification_policy
    )


def _invert_by_mapping_predicate(
    mappings: Iterable[MappingTypeVar],
    predicate: Reference,
    *,
    converter: curies.Converter,
    justification_policy: InversionJustificationPolicy | str | None = None,
) -> Iterable[MappingTypeVar]:
    yield from invert_by_predicate(
        mappings,
        predicate=lambda mapping: mapping.predicate == predicate,
        converter=converter,
        justification_policy=justification_policy,
    )


def invert_by_subject_prefix(
    mappings: Iterable[MappingTypeVar],
    subject_prefix: str,
    *,
    converter: curies.Converter,
    justification_policy: InversionJustificationPolicy | str | None = None,
) -> Iterable[MappingTypeVar]:
    """Invert mappings with the given subject prefix.

    :param mappings: An iterable of semantic mappings
    :param subject_prefix: Invert mappings that have this subject prefix
    :param converter: A converter function hashing the mapping to fill the
        "derives_from" field
    :param justification_policy: The policy for how the original evidence is mutated
        during inversion. Defaults to :class:`InversionDerivationPolicy.retain`, where
        the original justification is retained

    :returns: An iterable of semantic mappings, with the correct ones inverted

    >>> from curies import Converter
    >>> from curies.vocabulary import mapping_inversion
    >>> from sssom_pydantic import SemanticMapping, NOT, hash_triple_to_reference
    >>> converter = Converter.from_prefix_map(
    ...     {
    ...         "CHEBI": "http://purl.obolibrary.org/obo/CHEBI_",
    ...         "mesh": "http://id.nlm.nih.gov/mesh/",
    ...         "skos": "http://www.w3.org/2004/02/skos/core#",
    ...         "semapv": "https://w3id.org/semapv/vocab/",
    ...         "mapping": "https://w3id.org/mapping/",
    ...     }
    ... )
    >>> m1 = SemanticMapping.exact("mesh:C000089", "CHEBI:28646")
    >>> m1_inv = SemanticMapping.exact("CHEBI:28646", "mesh:C000089")
    >>> m2 = SemanticMapping.exact("CHEBI:10001", "mesh:C067604")
    >>> assert [m1_inv, m2] == list(invert_by_subject_prefix([m1, m2], "mesh", converter=converter))
    >>> m1_inv_derive = SemanticMapping.exact(
    ...     "CHEBI:28646",
    ...     "mesh:C000089",
    ...     justification=mapping_inversion,
    ...     derived_from=[hash_triple_to_reference(m1, converter)],
    ... )
    >>> assert [m1_inv_derive, m2] == list(
    ...     invert_by_subject_prefix(
    ...         [m1, m2], "mesh", converter=converter, justification_policy="derive"
    ...     )
    ... )
    """
    yield from invert_by_predicate(
        mappings,
        _subject_prefix(subject_prefix),
        converter=converter,
        justification_policy=justification_policy,
    )


def _subject_prefix(subject_prefix: str) -> SemanticMappingPredicate:
    def _func(m: MappingTypeVar) -> bool:
        return m.subject.prefix == subject_prefix

    return _func


def invert_by_object_prefix(
    mappings: Iterable[MappingTypeVar],
    object_prefix: str,
    *,
    converter: curies.Converter,
    justification_policy: InversionJustificationPolicy | str | None = None,
) -> Iterable[MappingTypeVar]:
    """Invert mappings with the given object prefix.

    :param mappings: An iterable of semantic mappings
    :param object_prefix: Invert mappings that have this object prefix
    :param converter: A converter function hashing the mapping to fill the
        "derives_from" field
    :param justification_policy: The policy for how the original evidence is mutated
        during inversion. Defaults to :class:`InversionDerivationPolicy.retain`, where
        the original justification is retained

    :returns: An iterable of semantic mappings, with the correct ones inverted

    >>> from curies import Converter
    >>> from curies.vocabulary import mapping_inversion
    >>> from sssom_pydantic import SemanticMapping, NOT, hash_triple_to_reference
    >>> converter = Converter.from_prefix_map(
    ...     {
    ...         "CHEBI": "http://purl.obolibrary.org/obo/CHEBI_",
    ...         "mesh": "http://id.nlm.nih.gov/mesh/",
    ...         "skos": "http://www.w3.org/2004/02/skos/core#",
    ...         "semapv": "https://w3id.org/semapv/vocab/",
    ...         "mapping": "https://w3id.org/mapping/",
    ...     }
    ... )
    >>> m1 = SemanticMapping.exact("mesh:C000089", "CHEBI:28646")
    >>> m1_inv = SemanticMapping.exact("CHEBI:28646", "mesh:C000089")
    >>> m2 = SemanticMapping.exact("CHEBI:10001", "mesh:C067604")
    >>> assert [m1_inv, m2] == list(invert_by_object_prefix([m1, m2], "CHEBI", converter=converter))
    >>> m1_inv_derive = SemanticMapping.exact(
    ...     "CHEBI:28646",
    ...     "mesh:C000089",
    ...     justification=mapping_inversion,
    ...     derived_from=[hash_triple_to_reference(m1, converter)],
    ... )
    >>> assert [m1_inv_derive, m2] == list(
    ...     invert_by_object_prefix(
    ...         [m1, m2], "CHEBI", converter=converter, justification_policy="derive"
    ...     )
    ... )
    """
    yield from invert_by_predicate(
        mappings,
        _object_prefix(object_prefix),
        converter=converter,
        justification_policy=justification_policy,
    )


def _object_prefix(object_prefix: str) -> SemanticMappingPredicate:
    def _func(m: MappingTypeVar) -> bool:
        return m.object.prefix == object_prefix

    return _func


def invert_by_prefix_pair(
    mappings: Iterable[MappingTypeVar],
    source_prefix: str,
    object_prefix: str,
    *,
    converter: curies.Converter,
    justification_policy: InversionJustificationPolicy | str | None = None,
) -> Iterable[MappingTypeVar]:
    """Invert mappings with the given subject and object (SO) prefixes.

    :param mappings: An iterable of semantic mappings
    :param source_prefix: Invert mappings that have this source prefix
    :param object_prefix: Invert mappings that have this object prefix
    :param converter: A converter function hashing the mapping to fill the
        "derives_from" field
    :param justification_policy: The policy for how the original evidence is mutated
        during inversion. Defaults to :class:`InversionDerivationPolicy.retain`, where
        the original justification is retained

    :returns: An iterable of semantic mappings, with the correct ones inverted

    >>> from curies import Converter
    >>> from curies.vocabulary import mapping_inversion
    >>> from sssom_pydantic import SemanticMapping, NOT, hash_triple_to_reference
    >>> converter = Converter.from_prefix_map(
    ...     {
    ...         "CHEBI": "http://purl.obolibrary.org/obo/CHEBI_",
    ...         "mesh": "http://id.nlm.nih.gov/mesh/",
    ...         "skos": "http://www.w3.org/2004/02/skos/core#",
    ...         "semapv": "https://w3id.org/semapv/vocab/",
    ...         "mapping": "https://w3id.org/mapping/",
    ...     }
    ... )
    >>> m1 = SemanticMapping.exact("mesh:C000089", "CHEBI:28646")
    >>> m1_inv = SemanticMapping.exact(
    ...     "CHEBI:28646",
    ...     "mesh:C000089",
    ... )
    >>> m2 = SemanticMapping.exact("CHEBI:10001", "mesh:C067604")
    >>> assert [m1_inv, m2] == list(
    ...     invert_by_prefix_pair([m1, m2], "mesh", "CHEBI", converter=converter)
    ... )
    >>> m1_inv_derive = SemanticMapping.exact(
    ...     "CHEBI:28646",
    ...     "mesh:C000089",
    ...     justification=mapping_inversion,
    ...     derived_from=[hash_triple_to_reference(m1, converter)],
    ... )
    >>> assert [m1_inv_derive, m2] == list(
    ...     invert_by_prefix_pair(
    ...         [m1, m2], "mesh", "CHEBI", converter=converter, justification_policy="derive"
    ...     )
    ... )
    """
    yield from invert_by_predicate(
        mappings,
        _so_prefixes(source_prefix, object_prefix),
        converter=converter,
        justification_policy=justification_policy,
    )


def _so_prefixes(source_prefix: str, object_prefix: str) -> SemanticMappingPredicate:
    def _func(m: MappingTypeVar) -> bool:
        return m.subject.prefix == source_prefix and m.object.prefix == object_prefix

    return _func


def merge_manual_curations(
    mappings: Iterable[MappingTypeVar],
    *,
    converter: curies.Converter,
    precision: int | None = None,
    confidence_model: ConfidenceModel | None = None,
) -> Iterable[MappingTypeVar]:
    r"""Merge manually curated mappings.

    :param mappings: An iterable of semantic mappings
    :param converter: A converter
    :param precision: the precision to round newly calculated confidences
    :param confidence_model: Which confidence model to use when aggregating mapping
        confidences.

        - mean aggregation is $\frac{1}{n} \sum_{i=1}^n c_i$
        - binomial aggregation is $1 - \prod_{i=1}^n (1 - c_i)$

    :returns: An iterable of semantic mappings, with manually curated mappings for the
        same mapping triple merged together based on :func:`estimate_confidence`

    .. note::

        The confidence estimation algorithm properly handles negative predicate
        modifiers as well as reviewer information.

    .. warning::

        This function partially scrambles the order of mappings. All non-merged mappings
        come out in normal order, followed by merged mappings.
    """
    manual_curated_index = defaultdict(list)
    for mapping in mappings:
        if mapping.justification == manual_mapping_curation:
            manual_curated_index[mapping.as_str_triple()].append(mapping)
        else:
            yield mapping
    for mapping_group in manual_curated_index.values():
        if len(mapping_group) == 1:
            yield mapping_group[0]
        else:
            yield _merge(
                mapping_group,
                converter=converter,
                precision=precision,
                confidence_model=confidence_model,
            )


def _merge(
    mappings: list[MappingTypeVar],
    *,
    converter: curies.Converter,
    precision: int | None = None,
    confidence_model: ConfidenceModel | None = None,
) -> MappingTypeVar:
    """Merge manually curated mappings with the same s-p-o triple."""
    authors = {author for mapping in mappings for author in mapping.authors or []}
    confidence = estimate_confidence(
        mappings, precision=precision, check=False, confidence_model=confidence_model
    )
    mapping = mappings[0]
    data = {
        "subject": mapping.subject,
        "predicate": mapping.predicate,
        "object": mapping.object,
        "justification": mapping.justification,  # will always be manual curation, by construction
        "authors": sorted(authors),
        "confidence": confidence,
        # TODO CC0 license?
        "derived_from": [hash_triple_to_reference(mapping, converter) for mapping in mappings],
    }
    # look for matching fields
    for slot_name in ["subject_source", "object_source"]:
        values = {getattr(mapping, slot_name) for mapping in mappings}
        if len(values) == 1 and (value := values.pop()) is not None:
            data[slot_name] = value
    return mapping.model_validate(data)


def filter_by_confidence(
    mappings: Iterable[MappingTypeVar], cutoff: float
) -> Iterable[MappingTypeVar]:
    """Filter by confidence."""
    for mapping in mappings:
        if mapping.confidence is not None and mapping.confidence < cutoff:
            continue
        yield mapping


if __name__ == "__main__":
    plot2d()
