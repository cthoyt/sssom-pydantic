"""Upload from SSSOM to Wikidata with Quickstatements v2.

The [Simple Standard for Sharing Ontology Mappings (SSSOM)](github.com/mapping-commons/sssom)
supports encoding equivalents, exact matches, cross-references, and other kinds of semantic
mappings in a simple, tabular format.
"""

from __future__ import annotations

from collections import defaultdict
from textwrap import dedent
from typing import Any

import bioregistry
import curies
import pandas as pd
import quickstatements_client
import wikidata_client
from curies.dataframe import get_df_unique_prefixes
from curies.vocabulary import exact_match
from quickstatements_client import Line, Qualifier, TextLine, TextQualifier

from sssom_pydantic import MappingSet, SemanticMapping

__all__ = [
    "get_quickstatements_lines",
    "get_quickstatements_lines_from_msdf",
    "open_quickstatements_tab",
    "open_quickstatements_tab_from_msdf",
]


def open_quickstatements_tab_from_msdf(
    mappings: list[SemanticMapping], converter: curies.Converter, metadata: MappingSet
) -> None:
    """Create a QuickStatements tab from mappings."""
    lines = get_quickstatements_lines_from_msdf(mappings, converter, metadata)
    quickstatements_client.lines_to_new_tab(lines)


def get_quickstatements_lines_from_msdf(
    mappings: list[SemanticMapping], converter: curies.Converter, metadata: MappingSet
) -> list[Line]:
    """Get lines for QuickStatements that can be used to upload SSSOM to Wikidata."""
    return get_quickstatements_lines(mappings, converter, metadata)


def open_quickstatements_tab(
    mappings: list[SemanticMapping], converter: curies.Converter, metadata: MappingSet
) -> None:
    """Create a QuickStatements tab from mappings."""
    lines = get_quickstatements_lines(mappings, converter, metadata)
    quickstatements_client.lines_to_new_tab(lines)


def get_quickstatements_lines(
    mappings: list[SemanticMapping], converter: curies.Converter, metadata: MappingSet
) -> list[Line]:
    """Get lines for QuickStatements that can be used to upload SSSOM to Wikidata."""
    mappings = [
        mapping
        for mapping in mappings
        if mapping.subject.prefix == "wikidata" and mapping.predicate == exact_match
    ]

    mapping_set_qualifiers = [
        # this sets the "reference URL" to the mapping set ID
        TextQualifier(predicate="S854", target=metadata["mapping_set_id"]),
        # could also add more metadata here
    ]

    prefix_to_wikidata = bioregistry.get_registry_map("wikidata")

    wikidata_ids = df["wikidata_id"].unique().tolist()

    wikidata_id_to_references = _get_wikidata_to_property_matches(
        wikidata_ids, df, converter, prefix_to_wikidata
    )

    wikidata_id_to_exact = _get_wikidata_to_exact_matches(wikidata_ids)

    lines: list[Line] = []
    for _, row in df.iterrows():
        subject = row["wikidata_id"]
        object_curie = row["object_id"]
        object_reference = converter.parse_curie(object_curie, strict=True)

        wikidata_prop = prefix_to_wikidata.get(object_reference.prefix)
        if wikidata_prop:
            existing_references = wikidata_id_to_references.get(subject, set())
            if object_reference not in existing_references:
                line = TextLine(
                    subject=subject,
                    predicate=wikidata_prop,
                    target=object_reference.identifier,
                    qualifiers=[*mapping_set_qualifiers, *_get_mapping_qualifiers(row)],
                )
                lines.append(line)
        else:
            object_uri = converter.expand_reference(object_reference, strict=True)
            existing_uris = wikidata_id_to_exact.get(subject, set())
            if object_uri not in existing_uris:
                line = TextLine(
                    subject=subject,
                    predicate="P2888",  # exact match
                    target=object_uri,
                    qualifiers=[*mapping_set_qualifiers, *_get_mapping_qualifiers(row)],
                )
                lines.append(line)

    return lines


def _get_wikidata_to_property_matches(
    wikidata_ids: list[str],
    df: pd.DataFrame,
    converter: curies.Converter,
    prefix_to_wikidata: dict[str, str] | None = None,
) -> dict[str, set[curies.Reference]]:
    if prefix_to_wikidata is None:
        prefix_to_wikidata = bioregistry.get_registry_map("wikidata")

    values = _values(wikidata_ids)
    rv: defaultdict[str, set[curies.Reference]] = defaultdict(set)
    for prefix in get_df_unique_prefixes(
        df, column="object_id", converter=converter, validate=True
    ):
        if wdp := prefix_to_wikidata.get(prefix):
            sparql = dedent(f"""\
                SELECT ?s ?o WHERE {{
                    VALUES ?s {{ {values} }}
                    ?s wdt:{wdp} ?o .
                }}
            """)
            for m in wikidata_client.query(sparql):
                rv[m["s"]].add(curies.ReferenceTuple(prefix, m["o"]))

    return dict(rv)


def _get_wikidata_to_exact_matches(wikidata_ids: list[str]) -> dict[str, set[str]]:
    sparql = dedent(f"""\
        SELECT ?s ?p ?o WHERE {{
            VALUES ?s {{ {_values(wikidata_ids)} }}
            ?s wdt:P2888 ?o .
        }}
    """)
    rv: defaultdict[str, set[str]] = defaultdict(set)
    for m in wikidata_client.query(sparql):
        rv[m["s"]].add(m["o"])
    return dict(rv)


def _values(wikidata_ids: list[str]) -> str:
    return " ".join("wd:" + x for x in wikidata_ids)


def _get_mapping_qualifiers(mapping: dict[str, Any]) -> list[Qualifier]:
    return []
