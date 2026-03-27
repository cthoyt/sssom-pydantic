"""Implementation of database in filesyste."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Literal, overload

from curies import Reference

from .repo import SemanticMappingRepository
from ..api import MappingSet, SemanticMapping
from ..io import append, read, write
from ..query import Query, filter_mappings, get_mappings

__all__ = ["FileSystemSemanticMappingRepository"]

DEFAULT_ID = "https://example.org/test.sssom.tsv"


class FileSystemSemanticMappingRepository(SemanticMappingRepository):
    """A repository that operates on the filesystem."""

    def __init__(
        self, path: str | Path, *, write_action: Literal["append", "overwrite"] = "overwrite"
    ) -> None:
        """Make it."""
        super().__init__()
        self.path = Path(path).resolve()
        if not self.path.is_file():
            import bioregistry

            write(
                [],
                path,
                converter=bioregistry.get_default_converter(),
                metadata=MappingSet(id=DEFAULT_ID),
            )
        self.mappings, self.converter, self.metadata = read(self.path)
        self.write_action = write_action

    def count_mappings(self, where_clauses: Query | None = None) -> int:
        """Count the number of mappings."""
        return sum(1 for _ in filter_mappings(self.mappings, where_clauses))

    def add_mappings(self, mappings: Iterable[SemanticMapping]) -> list[Reference]:
        """Add mappings to the repository."""
        mm = list(mappings)
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
        return [self.hash_mapping(m) for m in mm]

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
            raise ValueError
        return None

    def get_mappings(
        self,
        where_clauses: Query | None = None,
        limit: int | None = None,
        offset: int | None = None,
        order_by: str | None = None,
    ) -> Sequence[SemanticMapping]:
        """Get a sequence of mappings."""
        return get_mappings(self.mappings, where_clauses, limit, offset, order_by)
