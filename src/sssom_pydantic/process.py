"""Utilities for working with semantic mappings."""

from __future__ import annotations

import datetime
import itertools as itt
from collections import defaultdict
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any, Literal, TypeAlias, TypeVar, cast, get_args

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
    "UNSURE",
    "Call",
    "CanonicalMappingTuple",
    "Hasher",
    "Mark",
    "curate",
    "get_canonical_tuple",
    "publish",
    "remove_redundant_external",
    "remove_redundant_internal",
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
    :param key: A function that hashes the mappings. If not given, will
        only use the subject/object to has the mapping.
    :param scorer: A function that gives a score to a given mapping,
        where a higher score means it's more likely to be kept.
        Any function returning a comparable value can be used, but
        int/float are the easiest to understand.

    :returns: A list of mappings that have had duplicates dropped. This
        does not necessarily maintain order, since dictionary-based
        aggregation happens in the implementation.
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
    :param key: A function that hashes a given semantic mapping. If not given, one
        that uses the combination of subject + object will be used.
    :returns: A predicate that can be used to check if new mappings are already
        in the given mapping list(s)
    """
    if key is None:
        key = cast(Hasher[MappingTypeVar, HashTarget], get_canonical_tuple)

    skip_tuples: set[HashTarget] = {key(mapping) for mapping in itt.chain.from_iterable(mappings)}

    def _keep_mapping(mapping: MappingTypeVar) -> bool:
        return key(mapping) not in skip_tuples

    return _keep_mapping


UNSURE = "sssom-curator-unsure"
UNSURE_SUFFIX = f" ({UNSURE})"


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
    if mark == "unsure":
        if mapping.comment is None:
            comment = UNSURE
        elif UNSURE in mapping.comment:
            raise ValueError("this mapping has already been marked as unsure")
        else:
            comment = mapping.comment.rstrip() + UNSURE_SUFFIX
        return mapping.model_copy(update={"comment": comment})

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

    if mapping.comment is not None and UNSURE in mapping.comment:
        if mapping.comment == UNSURE:
            update["comment"] = None
        elif mapping.comment.endswith(UNSURE_SUFFIX):
            update["comment"] = mapping.comment.removesuffix(UNSURE_SUFFIX)
        else:
            raise NotImplementedError(
                f"not sure how to automatically remove annotation in comment: {mapping.comment}"
            )

    if mark in semantic_mapping_scopes:
        update["predicate"] = semantic_mapping_scopes[cast(SemanticMappingScope, mark)]
    elif mark == "incorrect":
        update["predicate_modifier"] = "Not"
    elif mark == "correct":
        pass  # nothing needed here!
    else:
        raise ValueError(f"invalid mark: {mark}")

    new_mapping = mapping.model_copy(update=update)
    return new_mapping


def publish(
    mapping: SemanticMapping,
    /,
    *,
    exists_action: Literal["error", "overwrite", "keep"] | None = None,
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
            raise ValueError(f"invalid exists_action: {exists_action}")
    rv = mapping.model_copy(
        update={"publication_date": date if date is not None else datetime.date.today()}
    )
    return rv
