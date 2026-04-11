"""Define an abstract repository."""

from __future__ import annotations

import datetime
from abc import ABC, abstractmethod
from collections.abc import Callable, Collection, Iterable, Sequence
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
from ..io import Metadata, read, write
from ..process import Mark, curate, estimate_confidence, publish, review
from ..query import Query, Sort

__all__ = ["CURIENotFoundError", "SemanticMappingRepository"]

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
        return self.semantic_mapping_hash(mapping, self.converter)

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
    def add_mappings(
        self, mappings: Iterable[SemanticMapping], *, progress: bool = False
    ) -> list[Reference]:
        """Add mappings to the database."""

    def read(
        self,
        path_or_url: str | Path,
        *,
        metadata: MappingSet | MappingSetRecord | Metadata | None = None,
        progress: bool = False,
        **kwargs: Any,
    ) -> list[Reference]:
        """Read mappings from a file into the database.

        :param path_or_url: The path or URL of the SSSOM TSV file to read
        :param metadata: Additional metadata, in case it's not embedded in the TSV
        :param progress: Show a progress bar on read and indexing?
        :param kwargs: Additional keyword arguments to pass to
            :func:`sssom_pydantic.read`

        :returns: The references for the mappings after they've been added to the
            database.
        """
        mappings, _converter, _metadata = read(
            path_or_url, metadata=metadata, converter=self.converter, progress=progress, **kwargs
        )
        # TODO check converter conflicts
        # TODO add progress to add_mappings?
        return self.add_mappings(mappings)

    def write(
        self,
        path: str | Path,
        *,
        metadata: MappingSet | Metadata | MappingSetRecord | None = None,
        exclude_columns: Collection[str] | None = None,
        where_clauses: Query | None = None,
        limit: int | None = None,
        offset: int | None = None,
        **kwargs: Any,
    ) -> None:
        """Write the database to a file."""
        # order_by is explicitly skipped since the writing function does this
        # in a canonical way
        mappings = self.get_mappings(where_clauses=where_clauses, limit=limit, offset=offset)
        write(
            mappings,
            path,
            metadata=metadata,
            converter=self.converter,
            exclude_columns=exclude_columns,
            **kwargs,
        )

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
        order_by: Sort | None = None,
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

    def review(
        self,
        reference: Reference,
        reviewers: Reference | list[Reference],
        score: float | None = None,
        date: datetime.date | None = None,
    ) -> Reference:
        """Review a mapping and return the new mapping's record.

        :param reference: A reference for a mapping record in the repository
        :param reviewers: A reviewer or list of reviewers
        :param score: The agreement score, where 1.0 means agree, 0.0 means unsure, and
            -1.0 means disagree
        :param date: The date of the review. Defaults to today.

        :returns: A new mapping record with new reviewer information. If there was
            already reviewer information, this will get overwritten.
        """
        return self._mutate(reference, review, reviewers=reviewers, score=score, date=date)

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


class CURIENotFoundError(ValueError):
    """Raise when a reference can't be found."""

    def __init__(self, reference: Reference) -> None:
        """Initialize the exception."""
        self.reference = reference

    def __str__(self) -> str:
        """Return a human-readable error message."""
        return f"could not find mapping with CURIE {self.reference.curie}"
