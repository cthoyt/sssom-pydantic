"""Ingest a DuckDB file from BridgeDB (schema v4)."""

from contextlib import closing
from pathlib import Path
from textwrap import dedent

import bioregistry
import duckdb
import pystow
from curies import Reference
from curies.vocabulary import has_dbxref, unspecified_matching_process

import sssom_pydantic
from sssom_pydantic import MappingSet, SemanticMapping
from sssom_pydantic.process import remove_redundant_internal

__all__ = [
    "from_bridgedb",
    "to_bridgedb",
]

DATASOURCES_URL = "https://bridgedb.github.io/datasources/datasources.tsv"

# bridge code (link.bridge) doesn't do anything
V4_SQL = dedent("""\
    SELECT
        link.codeLeft,
        link.idLeft,
        left_attribute.attrvalue as source_label,
        link.codeRight,
        link.idRight,
        right_attribute.attrvalue as object_label
    FROM link
    LEFT JOIN attribute left_attribute
        ON left_attribute.id = idLeft
        AND left_attribute.code = codeLeft
        AND left_attribute.attrname = 'Symbol'
    LEFT JOIN attribute right_attribute
        ON right_attribute.id = idRight
        AND right_attribute.code = codeRight
        AND right_attribute.attrname = 'Symbol'
""")


def from_bridgedb(path: str | Path, *, predicate: Reference | None = None) -> list[SemanticMapping]:
    """Load a DuckDB file from BridgeDB (schema v4)."""
    if predicate is None:
        predicate = has_dbxref.without_name()
    code_to_prefix = get_bridgedb_code_to_prefix()
    with closing(duckdb.connect(path, read_only=True)) as con:
        mappings = []
        for (
            subject_code,
            subject_id,
            subject_label,
            object_code,
            object_id,
            object_label,
        ) in con.sql(V4_SQL).fetchall():
            subject = bioregistry.StandardNamableReference(
                prefix=code_to_prefix[subject_code],
                identifier=subject_id,
                name=subject_label,
            )
            obj = bioregistry.StandardNamableReference(
                prefix=code_to_prefix[object_code],
                identifier=object_id,
                name=object_label,
            )
            if subject.curie == obj.curie:
                continue
            mapping = SemanticMapping(
                subject=subject,
                predicate=predicate,
                object=obj,
                justification=unspecified_matching_process,
            )
            mappings.append(mapping)

    # needed since the source has bananas first (e.g., CHEBI:CHEBI:1234)
    mappings = remove_redundant_internal(mappings)
    return mappings


def _from_bridgedb_v3(path: Path) -> list[SemanticMapping]:
    raise NotImplementedError


def get_bridgedb_code_to_prefix(*, refresh: bool = False) -> dict[str, str]:
    """Get the BridgeDB code to Semantic Farm prefix mapping."""
    datasources_df = pystow.ensure_csv("bridgedb", url=DATASOURCES_URL, force=refresh)
    code_column = datasources_df.columns[1]
    semantic_farm_column = datasources_df.columns[12]
    datasources_df = datasources_df[
        datasources_df[code_column].notna() & datasources_df[semantic_farm_column].notna()
    ]
    code_to_prefix = dict(datasources_df[[code_column, semantic_farm_column]].values)
    return code_to_prefix


def to_bridgedb(mappings: list[SemanticMapping], path: Path) -> None:
    """Create a BridgeDB DuckDB file."""
    with closing(duckdb.connect(path, read_only=False)):
        raise NotImplementedError


def _main() -> None:
    mappings = from_bridgedb(
        "/Users/cthoyt/dev/sssom-pydantic/tests/test_contrib/test_bridgedb/aminoacids_duckdb_db4.bridge",
    )
    # TODO construct mapping set from VOID headers, if they're in the duckdb?
    mapping_set = MappingSet(title="amino acids", id="https://example.org/test.sssom.tsv")
    sssom_pydantic.write(
        mappings,
        "/Users/cthoyt/dev/sssom-pydantic/tests/test_contrib/test_bridgedb/aminoacids_duckdb_db4.sssom.tsv",
        metadata=mapping_set,
        converter=bioregistry.get_preferred_converter(),
    )


if __name__ == "__main__":
    _main()
