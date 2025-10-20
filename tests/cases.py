"""Test constants."""

from __future__ import annotations

from typing import Any

from curies import NamedReference, Reference
from curies.vocabulary import exact_match, manual_mapping_curation

from sssom_pydantic.api import SemanticMapping
from sssom_pydantic.models import Record

__all__ = [
    "P1",
    "R1",
    "R2",
    "_m",
    "_r",
]

R1 = NamedReference(prefix="mesh", identifier="C000089", name="ammeline")
R2 = NamedReference(prefix="chebi", identifier="28646", name="ammeline")
P1 = Reference(prefix="skos", identifier="exactMatch")


def _m(**kwargs: Any) -> SemanticMapping:
    """Construct a base semantic mapping."""
    return SemanticMapping(
        subject=R1,
        predicate=P1,
        object=R2,
        justification=manual_mapping_curation,
        **kwargs,
    )


def _r(**kwargs: Any) -> Record:
    """Construct a base record."""
    return Record(
        subject_id=R1.curie,
        subject_label=R1.name,
        predicate_id=exact_match.curie,
        object_id=R2.curie,
        object_label=R2.name,
        mapping_justification=manual_mapping_curation.curie,
        **kwargs,
    )
