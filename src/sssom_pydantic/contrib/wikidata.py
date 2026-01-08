"""Upload from SSSOM to Wikidata with Quickstatements v2.

The [Simple Standard for Sharing Ontology Mappings (SSSOM)](github.com/mapping-commons/sssom)
supports encoding equivalents, exact matches, cross-references, and other kinds of semantic
mappings in a simple, tabular format.

Original proposal here: https://doi.org/10.5281/zenodo.17662905
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Collection, Iterable
from itertools import chain
from textwrap import dedent
from typing import TYPE_CHECKING, Any, TypeVar

import bioregistry
import curies
import curies.vocabulary as cv
import quickstatements_client
import wikidata_client
from curies import Converter
from quickstatements_client import EntityQualifier, Line, Qualifier, TextLine, TextQualifier

from sssom_pydantic import MappingSet, SemanticMapping, read

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "get_quickstatements_lines",
    "open_quickstatements_tab",
    "read_to_quickstatements_lines",
    "read_to_quickstatements_tab",
]

X = TypeVar("X")
Y = TypeVar("Y")


def read_to_quickstatements_tab(path_or_url: str | Path, **kwargs: Any) -> None:
    """Read an SSSOM file and open the Quickstatements v2 uploader with the web browser."""
    mappings, converter, metadata = read(path_or_url, **kwargs)
    open_quickstatements_tab(mappings, converter, metadata)


def open_quickstatements_tab(
    mappings: list[SemanticMapping], converter: curies.Converter, metadata: MappingSet
) -> None:
    """Create a QuickStatements tab from mappings."""
    lines = get_quickstatements_lines(mappings, converter, metadata)
    quickstatements_client.lines_to_new_tab(lines)


def read_to_quickstatements_lines(path_or_url: str | Path, **kwargs: Any) -> list[Line]:
    """Read an SSSOM file and get QuickStatements v2 lines."""
    mappings, converter, metadata = read(path_or_url, **kwargs)
    return get_quickstatements_lines(mappings, converter, metadata)


def get_quickstatements_lines(
    mappings: list[SemanticMapping], converter: curies.Converter, mapping_set: MappingSet
) -> list[Line]:
    """Get lines for QuickStatements that can be used to upload SSSOM to Wikidata."""
    mappings = [
        mapping
        for mapping in mappings
        if mapping.subject.prefix == "wikidata" and mapping.predicate_modifier is None
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
    # ChEBI get mapped to P683. We still want to keep prefixes that
    # don't have a Wikidata property since we can construct URIs
    # with the exact match (P2888) predicate.
    object_prefix_to_wikidata: dict[str, str | None] = {
        mapping.object.prefix: prefix_to_wikidata.get(mapping.object.prefix) for mapping in mappings
    }

    wikidata_ids: set[str] = {mapping.subject.identifier for mapping in mappings}

    wikidata_id_to_references = _get_wikidata_to_property_matches(
        wikidata_ids, object_prefix_to_wikidata
    )

    wikidata_id_to_exact = _get_wikidata_to_exact_matches(wikidata_ids, converter)

    orcid_to_wikidata = _get_orcid_to_wikidata(mappings)

    # filter out all mappings that can already be found on wikidata
    mappings = [
        mapping
        for mapping in mappings
        if mapping.object not in wikidata_id_to_references.get(mapping.subject.identifier, set())
    ]

    lines = []
    for mapping in mappings:
        if wikidata_property_id := prefix_to_wikidata.get(mapping.object.prefix):
            if mapping.object in wikidata_id_to_references.get(mapping.subject.identifier, set()):
                continue
            line = TextLine(
                subject=mapping.subject.identifier,
                predicate=wikidata_property_id,
                target=mapping.object.identifier,
                qualifiers=[
                    *mapping_set_qualifiers,
                    *_get_mapping_qualifiers(mapping, orcid_to_wikidata),
                ],
            )
            lines.append(line)
        else:
            if mapping.object in wikidata_id_to_exact.get(mapping.subject.identifier, set()):
                continue
            object_uri = converter.expand_reference(mapping.object)
            if object_uri is None:
                continue
            line = TextLine(
                subject=mapping.subject.identifier,
                predicate="P2888",  # exact match
                target=object_uri,
                qualifiers=[
                    *mapping_set_qualifiers,
                    *_get_mapping_qualifiers(mapping, orcid_to_wikidata),
                ],
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
        SELECT ?s ?o WHERE {{
            VALUES ?s {{ {_values_for_sparql(wikidata_ids)} }}
            ?s wdt:P2888 ?o .
        }}
    """)
    rv: defaultdict[str, set[curies.Reference]] = defaultdict(set)
    for m in wikidata_client.query(sparql):
        if reference := converter.parse(m["o"]):
            rv[m["s"]].add(reference.to_pydantic())
    return dict(rv)


def _values_for_sparql(wikidata_ids: Collection[str]) -> str:
    return " ".join("wd:" + x for x in sorted(wikidata_ids))


def _get_wikidata_license(mapping_license: str | None) -> str | None:
    if mapping_license is None:
        return None
    return None


def _get_orcid_to_wikidata(mappings: Iterable[SemanticMapping]) -> dict[str, str]:
    orcids: set[str] = {
        person.identifier
        for mapping in mappings
        # TODO creators?
        for person in chain(mapping.authors or [], mappings.reviewers or [])
        if person.prefix == "orcid"
    }
    return wikidata_client.get_entities_by_orcid(orcids)


SKOS_TO_WIKIDATA: dict[curies.Reference, str] = {
    cv.exact_match: "Q39893449",  # see https://www.wikidata.org/wiki/Q39893449
    cv.related_match: "Q39894604",  # see https://www.wikidata.org/wiki/Q39894604
    cv.close_match: "Q39893184",  # see https://www.wikidata.org/wiki/Q39893184
    cv.narrow_match: "Q39893967",  # see https://www.wikidata.org/wiki/Q39893967
    cv.broad_match: "Q39894595",  # see https://www.wikidata.org/wiki/Q39894595
}


def _get_mapping_qualifiers(
    mapping: SemanticMapping, orcid_to_wikidata: dict[str, str]
) -> list[Qualifier]:
    rv = []

    # see https://www.wikidata.org/wiki/Property:S275
    if wikidata_license_id := _get_wikidata_license(mapping.license):
        rv.append(EntityQualifier(predicate="S275", target=wikidata_license_id))

    # see https://www.wikidata.org/wiki/Property:P4390
    if ss := SKOS_TO_WIKIDATA.get(mapping.predicate):
        rv.append(EntityQualifier(predicate="S4390", target=ss))

    for author in mapping.authors:
        if author.prefix == "orcid" and (
            author_wikidata_id := orcid_to_wikidata.get(author.identifier)
        ):
            rv.append(EntityQualifier(predicate="S50", target=author_wikidata_id))

    for reviewer in mapping.reviewers or []:
        if reviewer.prefix == "orcid" and (
            reviewer_wikidata_id := orcid_to_wikidata.get(reviewer.identifier)
        ):
            rv.append(EntityQualifier(predicate="S4032", target=reviewer_wikidata_id))

    return rv
