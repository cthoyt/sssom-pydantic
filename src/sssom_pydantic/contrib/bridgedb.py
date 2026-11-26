"""I/O for BridgeDB (DuckDB schema v4)."""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
from textwrap import dedent

import bioregistry
import duckdb
import pandas as pd
import pystow
from curies import NamableReference, Reference
from curies.vocabulary import has_dbxref, unspecified_matching_process

from sssom_pydantic import SemanticMapping
from sssom_pydantic.process import remove_redundant_internal

__all__ = [
    "from_bridgedb",
    "to_bridgedb",
]

#: A URL for the BridgeDB datasource to Bioregistry prefix table
DATASOURCES_URL = "https://bridgedb.github.io/datasources/datasources.tsv"

# bridge code (link.bridge) doesn't do anything
SQL = dedent("""\
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
    """Load a BridgeDB file encoded in DuckDB schema v4.

    :param path: Path to BridgeDB file. See https://data.bridgedb.org/gene_database/ for
        first-party BridgeDB files
    :param predicate: The predicate to use for mappings. If not specified, defaults to
        :data:`curies.vocabulary.has_dbxref`

    :returns: A list of semantic mapping objects
    """
    if predicate is None:
        predicate = has_dbxref.without_name()
    with closing(duckdb.connect(path, read_only=True)) as con:
        return from_bridgedb_connection(con, predicate=predicate)


def from_bridgedb_connection(
    connection: duckdb.DuckDBPyConnection, *, predicate: Reference | None = None
) -> list[SemanticMapping]:
    """Load a BridgeDB file (DuckDB schema v4) that has already been opened with :func:`duckdb.connect`."""
    if predicate is None:
        predicate = has_dbxref.without_name()
    code_to_prefix = get_bridgedb_code_to_prefix()
    mappings = []
    for (
        subject_code,
        subject_id,
        subject_label,
        object_code,
        object_id,
        object_label,
    ) in connection.sql(SQL).fetchall():
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


def to_bridgedb(mappings: list[SemanticMapping], path: str | Path) -> None:
    """Create a BridgeDB file encoded in DuckDB schema v4."""
    with closing(duckdb.connect(path, read_only=False)) as conn:
        _to_bridgedb(mappings, conn)


DATANODE_COLUMNS = ["id", "code", "isPrimary"]
LINK_COLUMNS = ["idLeft", "codeLeft", "idRight", "codeRight", "bridge"]
ATTRIBUTE_COLUMNS = ["id", "code", "isPrimary", "attrname", "attrvalue"]


def _get_not_primary(mappings: list[SemanticMapping]) -> set[Reference]:
    return set()


def _to_bridgedb(mappings: list[SemanticMapping], conn: duckdb.DuckDBPyConnection) -> None:
    references: set[NamableReference] = {
        reference for mapping in mappings for reference in mapping.get_prefixes()
    }
    prefix_to_code = {code: prefix for prefix, code in get_bridgedb_code_to_prefix().items()}

    # TODO precalculate isPrimary
    not_primary: set[Reference] = set()

    datanode_rows = [
        (prefix_to_code[reference.prefix], reference.identifier, reference not in not_primary)
        for reference in references
    ]
    datanode_df = pd.DataFrame(datanode_rows, columns=DATANODE_COLUMNS)

    link_rows = [
        (
            prefix_to_code[reference.prefix],
            reference.identifier,
            reference not in not_primary,
            "Symbol",
            reference.name,
        )
        for reference in references
        if reference.name is not None
    ]
    link_df = pd.DataFrame(link_rows, columns=LINK_COLUMNS)
    attribute_rows = [
        (
            prefix_to_code[mapping.subject.prefix],
            mapping.subject.identifier,
            prefix_to_code[mapping.object.prefix],
            mapping.object.identifier,
            None,  # TODO what should go in bridge spot?
        )
        for mapping in mappings
        if mapping.subject.prefix in prefix_to_code and mapping.object.prefix in prefix_to_code
    ]
    attribute_df = pd.DataFrame(attribute_rows, columns=ATTRIBUTE_COLUMNS)

    conn.append("datanode", datanode_df)
    conn.append("attribute", attribute_df)
    conn.append("link", link_df)


def _main() -> None:
    import sssom_pydantic
    from sssom_pydantic import MappingSet

    p1 = "/Users/cthoyt/dev/sssom-pydantic/tests/test_contrib/test_bridgedb/aminoacids_duckdb_db4.bridge"

    mappings = from_bridgedb(p1)
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
