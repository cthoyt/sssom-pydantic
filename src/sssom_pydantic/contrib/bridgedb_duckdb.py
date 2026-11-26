"""Ingest a DuckDB file from BridgeDB (schema v4)."""

from pathlib import Path

from typing_extensions import Literal, TypeAlias

from sssom_pydantic import SemanticMapping

__all__ = [
    "BridgeDBVersion",
    "from_bridgedb",
]

BridgeDBVersion: TypeAlias = Literal["3", "4"]


def from_bridgedb(path: Path) -> list[SemanticMapping]:
    """Load a DuckDB file from BridgeDB (schema v4)."""


def _from_bridgedb_v3(path: Path) -> list[SemanticMapping]:
    pass


def _from_bridgedb_v4(path: Path) -> list[SemanticMapping]:
    pass
