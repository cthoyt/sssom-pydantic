"""Implementation of database in filesyste."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Literal, overload

import curies
from curies import Reference

from .repo import CURIENotFoundError, SemanticMappingRepository
from ..api import (
    MappingSet,
    SemanticMapping,
    SemanticMappingHash,
)
from ..io import append, read, write
from ..query import Query, Sort, count_unique_entities, filter_mappings, get_mappings

__all__ = ["FileSystemSemanticMappingRepository"]

DEFAULT_ID = "https://example.org/test.sssom.tsv"


class FileSystemSemanticMappingRepository(SemanticMappingRepository):
    """A repository that operates on the filesystem."""

    mappings: list[SemanticMapping]

    def __init__(
        self,
        path: str | Path,
        *,
        write_action: Literal["append", "overwrite"] = "overwrite",
        semantic_mapping_hash: SemanticMappingHash | None = None,
        converter: curies.Converter | None = None,
    ) -> None:
        """Make it."""
        self.path = Path(path).resolve()
        if not self.path.is_file():
            if converter is None:
                import bioregistry

                converter = bioregistry.get_default_converter()

            self.mappings = []
            self.metadata = MappingSet(id=DEFAULT_ID)
            write(
                [],
                path,
                converter=converter,
                metadata=self.metadata,
            )
        else:
            self.mappings, converter, self.metadata = read(self.path)
        super().__init__(semantic_mapping_hash=semantic_mapping_hash, converter=converter)
        self.write_action = write_action

    def count_mappings(self, query: Query | None = None) -> int:
        """Count the number of mappings."""
        return sum(1 for _ in filter_mappings(self.mappings, query, converter=self.converter))

    def count_predictions(self, query: Query | None = None) -> int:
        raise NotImplementedError

    def count_entities(self, query: Query | None = None) -> int:
        """Count the number of unique entities appearing in the subjects and objects of mappings."""
        return count_unique_entities(
            filter_mappings(self.mappings, query, converter=self.converter)
        )

    def add_mappings(
        self, mappings: Iterable[SemanticMapping], *, progress: bool = False
    ) -> list[Reference]:
        """Add mappings to the repository."""
        mm = []
        hashes = []
        for mapping in mappings:
            hsh = self.hash_mapping(mapping)
            hashes.append(hsh)
            mapping = mapping.model_copy(update={"record": hsh})
            mm.append(mapping)

        self.mappings.extend(mm)
        match self.write_action:
            case "append":
                append(mm, self.path, converter=self.converter, metadata=self.metadata)
            case "overwrite":
                write(
                    self.mappings,
                    self.path,
                    converter=self.converter,
                    metadata=self.metadata,
                    sort=True,
                )
        return hashes

    def delete_mapping(self, reference: Reference | SemanticMapping) -> None:
        """Delete a mapping."""
        reference = self._ensure(reference)
        self.mappings = [
            mapping for mapping in self.mappings if self.hash_mapping(mapping) != reference
        ]

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

    def get_mapping(self, reference: Reference, *, strict: bool = False) -> SemanticMapping | None:
        """Get a mapping."""
        reference = self._ensure(reference)
        mappings = [mapping for mapping in self.mappings if self.hash_mapping(mapping) == reference]
        if mappings:
            return mappings[0]
        if strict:
            raise CURIENotFoundError(reference)
        return None

    def get_mappings(
        self,
        query: Query | None = None,
        limit: int | None = None,
        offset: int | None = None,
        order_by: Sort | None = None,
    ) -> Sequence[SemanticMapping]:
        """Get a sequence of mappings."""
        return get_mappings(
            self.mappings,
            query,
            limit=limit,
            offset=offset,
            order_by=order_by,
            converter=self.converter,
        )
