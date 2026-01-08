"""Upload from SSSOM to Wikidata with Quickstatements v2.

The [Simple Standard for Sharing Ontology Mappings (SSSOM)](github.com/mapping-commons/sssom)
supports encoding equivalents, exact matches, cross-references, and other kinds of semantic
mappings in a simple, tabular format.

Original proposal here: https://doi.org/10.5281/zenodo.17662905
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Collection
from textwrap import dedent
from typing import TypeVar

import bioregistry
import curies
import quickstatements_client
import wikidata_client
from curies import Converter
from curies.vocabulary import exact_match
from quickstatements_client import Line, Qualifier, TextLine, TextQualifier

from sssom_pydantic import MappingSet, SemanticMapping

__all__ = [
    "get_quickstatements_lines",
    "get_quickstatements_lines_from_msdf",
    "open_quickstatements_tab",
    "open_quickstatements_tab_from_msdf",
]

X = TypeVar("X")
Y = TypeVar("Y")


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
    mappings: list[SemanticMapping], converter: curies.Converter, mapping_set: MappingSet
) -> list[Line]:
    """Get lines for QuickStatements that can be used to upload SSSOM to Wikidata."""
    mappings = [
        mapping
        for mapping in mappings
        if mapping.subject.prefix == "wikidata" and mapping.predicate == exact_match
    ]

    # construct a list of qualifiers that apply to all mappings in the
    # mapping set, such as the mapping set ID, creators, etc.
    mapping_set_qualifiers = [
        # this sets the "reference URL" to the mapping set ID
        TextQualifier(predicate="S854", target=mapping_set.id),
        # could also add more metadata here
    ]

    # Get the mapping from Bioregistry prefixes to Wikidata prefixes,
    # e.g., `chebi` maps to `P683`
    prefix_to_wikidata = bioregistry.get_registry_map("wikidata")

    # This makes a mapping from the prefixes appearing in mappings to
    # Wikidata properties. For example, mappings whose objects use
    # ChEBI get mapped to P683
    object_prefix_to_wikidata: dict[str, str | None] = {
        mapping.object.prefix: prefix_to_wikidata.get(mapping.object.prefix) for mapping in mappings
    }

    wikidata_ids: set[str] = {mapping.subject.identifier for mapping in mappings}

    wikidata_id_to_references = _get_wikidata_to_property_matches(
        wikidata_ids, object_prefix_to_wikidata
    )

    wikidata_id_to_exact = _get_wikidata_to_exact_matches(wikidata_ids, converter)

    wikidata_id_to_references = _combine(wikidata_id_to_references, wikidata_id_to_exact)

    # filter out all mappings that can already be found on wikidata
    mappings = [
        mapping
        for mapping in mappings
        if mapping.object not in wikidata_id_to_references.get(mapping.subject.identifier, set())
    ]

    lines = []
    for mapping in mappings:
        wikidata_prop = prefix_to_wikidata.get(mapping.object.prefix)
        if wikidata_prop:
            line = TextLine(
                subject=mapping.subject.identifier,
                predicate=wikidata_prop,
                target=mapping.object.identifier,
                qualifiers=[*mapping_set_qualifiers, *_get_mapping_qualifiers(mapping)],
            )
            lines.append(line)
        else:
            object_uri = converter.expand_reference(mapping.object, strict=True)
            line = TextLine(
                subject=mapping.subject.identifier,
                predicate="P2888",  # exact match
                target=object_uri,
                qualifiers=[*mapping_set_qualifiers, *_get_mapping_qualifiers(mapping)],
            )
            lines.append(line)
    return lines


def _get_wikidata_to_property_matches(
    wikidata_ids: Collection[str],
    prefix_to_wikidata: dict[str, str | None],
) -> dict[str, set[curies.Reference]]:
    values = _values_for_sparql(wikidata_ids)
    rv: defaultdict[str, set[curies.Reference]] = defaultdict(set)

    for prefix, wikidata_property_id in prefix_to_wikidata.items():
        if wikidata_property_id is None:
            continue
        sparql = dedent(f"""\
            SELECT ?s ?o WHERE {{
                VALUES ?s {{ {values} }}
                ?s wdt:{wikidata_property_id} ?o .
            }}
        """)
        for record in wikidata_client.query(sparql):
            rv[record["s"]].add(curies.Reference(prefix=prefix, identifier=record["o"]))
    return dict(rv)


def _get_wikidata_to_exact_matches(
    wikidata_ids: Collection[str], converter: Converter
) -> dict[str, set[curies.Reference]]:
    # P2888 is "exact match", see https://www.wikidata.org/wiki/Property:P2888
    sparql = dedent(f"""\
        SELECT ?s ?p ?o WHERE {{
            VALUES ?s {{ {_values_for_sparql(wikidata_ids)} }}
            ?s wdt:P2888 ?o .
        }}
    """)
    rv: defaultdict[str, set[curies.Reference]] = defaultdict(set)
    for m in wikidata_client.query(sparql):
        if reference := converter.parse(m["o"]):
            rv[m["s"]].add(reference.to_pydantic())
    return dict(rv)


def _combine(*args: dict[X, set[Y]]) -> dict[X, set[Y]]:
    rv = defaultdict(set)
    for d in args:
        for k, values in d.items():
            rv[k].update(values)
    return dict(rv)


def _values_for_sparql(wikidata_ids: Collection[str]) -> str:
    return " ".join("wd:" + x for x in sorted(wikidata_ids))


def _get_mapping_qualifiers(mapping: SemanticMapping) -> list[Qualifier]:
    return []
