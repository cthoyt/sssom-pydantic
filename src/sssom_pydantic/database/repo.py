"""Define an abstract repository."""

from __future__ import annotations

import datetime
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Any, Concatenate, Literal, ParamSpec, cast, overload

import curies
from curies import Converter, Reference

from ..api import (
    MappingSet,
    MappingSetRecord,
    SemanticMapping,
    SemanticMappingHash,
    mapping_hash_v1,
)
from ..io import Metadata, read
from ..process import Mark, curate, estimate_confidence, publish
from ..query import Query

__all__ = ["SemanticMappingRepository"]

P = ParamSpec("P")


class SemanticMappingRepository(ABC):
    """Interact with a repository of semantic mappings."""

    converter: curies.Converter

    def __init__(
        self,
        *,
        semantic_mapping_hash: SemanticMappingHash | None = None,
        converter: Converter,
    ) -> None:
        """Initialize the repository."""
        self.semantic_mapping_hash = semantic_mapping_hash or mapping_hash_v1
        self.converter = converter

    def hash_mapping(self, mapping: SemanticMapping) -> Reference:
        """Get a reference for the mapping."""
        return self.semantic_mapping_hash(mapping)

    def _ensure(self, reference: Reference | SemanticMapping) -> Reference:
        if isinstance(reference, SemanticMapping):
            return self.hash_mapping(reference)
        return reference

    @abstractmethod
    def count_mappings(self, where_clauses: Query | None = None) -> int:
        """Count the mappings in the database."""

    @abstractmethod
    def count_entities(self, where_clauses: Query | None = None) -> int:
        """Count the number of entities appearing as subjects/objects in the database."""

    def add_mapping(self, mapping: SemanticMapping) -> Reference:
        """Add a mapping to the database."""
        rv = self.add_mappings([mapping])
        return rv[0]

    @abstractmethod
    def add_mappings(self, mappings: Iterable[SemanticMapping]) -> list[Reference]:
        """Add mappings to the database."""

    def read(
        self,
        path: str | Path,
        *,
        metadata: MappingSet | MappingSetRecord | Metadata | None = None,
        progress: bool = False,
        **kwargs: Any,
    ) -> list[Reference]:
        """Read mappings from a file into the database."""
        mappings, _converter, _metadata = read(
            path, metadata=metadata, converter=self.converter, progress=progress, **kwargs
        )
        # TODO check converter conflicts
        # TODO add progress to add_mappings?
        return self.add_mappings(mappings)

    @abstractmethod
    def delete_mapping(self, reference: Reference | SemanticMapping) -> None:
        """Delete a mapping from the database."""

    # docstr-coverage:excused `overload`
    @overload
    def get_mapping(
        self, reference: Reference, *, strict: Literal[True] = ...
    ) -> SemanticMapping: ...

    # docstr-coverage:excused `overload`
    @overload
    def get_mapping(
        self, reference: Reference, *, strict: Literal[False] = ...
    ) -> SemanticMapping | None: ...

    @abstractmethod
    def get_mapping(self, reference: Reference, *, strict: bool = False) -> SemanticMapping | None:
        """Get a mapping."""

    @abstractmethod
    def get_mappings(
        self,
        where_clauses: Query | None = None,
        *,
        limit: int | None = None,
        offset: int | None = None,
        order_by: str | None = None,
    ) -> Sequence[SemanticMapping]:
        """Get mappings."""

    def curate(
        self,
        reference: Reference,
        authors: Reference | list[Reference],
        mark: Mark,
        confidence: float | None = None,
        add_date: bool = True,
        **kwargs: Any,
    ) -> Reference:
        """Curate a mapping and return the new mapping's record."""
        if isinstance(authors, Reference):
            authors = [authors]
        return self._mutate(
            reference,
            curate,
            authors=authors,
            mark=mark,
            confidence=confidence,
            add_date=add_date,
            **kwargs,
        )

    def publish(
        self,
        reference: Reference,
        date: datetime.date | None = None,
    ) -> Reference:
        """Publish a mapping and return the new mapping's record."""
        return self._mutate(reference, publish, date=date)

    def _mutate(
        self,
        reference: Reference,
        f: Callable[Concatenate[SemanticMapping, P], SemanticMapping],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> Reference:
        mapping = self.get_mapping(reference)
        if mapping is None:
            raise KeyError
        new_mapping = f(mapping, *args, **kwargs)
        new_mapping = new_mapping.model_copy(update={"record": self.hash_mapping(new_mapping)})
        self.add_mapping(new_mapping)
        self.delete_mapping(reference)
        return cast(Reference, new_mapping.record)

    def estimate_confidence(self, triple_id: str) -> float:
        """Calculate confidence for a triple across all mappings."""
        query = Query(triple_id=triple_id)
        mappings = self.get_mappings(query)
        confidence = estimate_confidence(mappings, check=False)
        return confidence
