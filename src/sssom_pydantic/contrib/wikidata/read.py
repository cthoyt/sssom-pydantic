"""Read operations for Wikidata."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Collection, Iterable
from textwrap import dedent

import curies
import wikidata_client
from curies import Converter, NamableReference
from curies import vocabulary as cv
from tqdm import tqdm

from sssom_pydantic import SemanticMapping
from sssom_pydantic.constants import CC0_URL

from .constants import WIKIDATA_TO_SKOS

__all__ = [
    "get_property_matches_by_ids",
    "get_exact_matches_by_ids",
    "get_mappings_by_property",
    "get_equivalent_property_mappings",
]

EQUIVALENT_PROPERTY_SPARQL = """\
    SELECT ?item ?itemLabel ?val ?mappingType ?mappingTypeLabel
    WHERE {
        ?item p:P1628 ?statement .
        ?statement ps:P1628 ?val .
        OPTIONAL { ?statement pq:P4390 ?mappingType }
        SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],mul,en" . }
    }
"""

#: A wikidata entry about itself
WIKIDATA_SOURCE_R = NamableReference(prefix="wikidata", identifier="Q2013", name="Wikidata")


def get_equivalent_property_mappings(
    *, converter: Converter | None = None
) -> list[SemanticMapping]:
    """Get mappings from Wikidata encoded in "equivalent property" triples.

    :param converter: A converter for parsing the URIs of the objects of equivalent
        property triples.

    :returns: A list of semantic mappings

    .. note::

        In September 2026, there were 861 results, with 4 that included mapping types.
    """
    converter = _ensure_converter(converter)
    rv = []
    for row in wikidata_client.query(EQUIVALENT_PROPERTY_SPARQL):
        object_reference_tuple = converter.parse_uri(row["val"])
        if object_reference_tuple is None:
            tqdm.write(f"failed to parse {row['val']}")
            continue
        mapping = SemanticMapping(
            subject=NamableReference(
                prefix="wikidata", identifier=row["item"], name=row["itemLabel"]
            ),
            predicate=_handle_mapping_type(row.get("mappingType"), cv.equivalent_property),
            object=object_reference_tuple.to_pydantic(),
            justification=cv.unspecified_matching_process,
            license=CC0_URL,
            source=WIKIDATA_SOURCE_R,
        )
        rv.append(mapping)
    return rv


def _handle_mapping_type(
    mapping_predicate_qid: str | None, default: curies.Reference
) -> curies.Reference:
    if mapping_predicate_qid is None:
        return default
    return WIKIDATA_TO_SKOS.get(mapping_predicate_qid, default)


def _get_mapping_sparql(property_id: str) -> str:
    return dedent(f"""\
        SELECT ?entity ?entityLabel ?id ?mappingType
        WHERE {{
            ?entity p:{property_id} ?statement .
            ?statement ps:{property_id} ?id .
            OPTIONAL {{ ?statement pq:P4390 ?mappingType }}
            SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],mul,en". }}
        }}
    """)


def get_mappings_by_property(
    property_id: str | None,
    prefix: str | None,
    *,
    confidence: float = 0.99,
    timeout: int = 300,
    endpoint: str | None = None,
) -> Iterable[SemanticMapping]:
    """Get mappings from Wikidata."""
    for row in wikidata_client.query(
        _get_mapping_sparql(property_id), timeout=timeout, endpoint=endpoint
    ):
        if not row["entity"].startswith("Q"):
            continue
        try:
            obj = NamableReference(prefix=prefix, identifier=_clean_xref_id(prefix, row["id"]))
        except ValueError:
            continue
        yield SemanticMapping(
            subject=NamableReference(
                prefix="wikidata", identifier=row["entity"], name=row["entityLabel"]
            ),
            predicate=_handle_mapping_type(row.get("mappingType"), cv.exact_match),
            object=obj,
            justification=cv.unspecified_matching_process,
            license=CC0_URL,
            confidence=confidence,
            source=WIKIDATA_SOURCE_R,
        )


def _clean_xref_id(prefix: str, identifier: str) -> str:
    if identifier.lower().startswith(f"{prefix}_"):
        identifier = identifier[len(prefix) + 1 :]
    return identifier


def get_property_matches_by_ids(
    wikidata_ids: Collection[str],
    prefix_to_wikidata: dict[str, str | None],
) -> dict[str, set[curies.Reference]]:
    """Get all property-based mappings for the given IDs across all prefix/properties.

    :param wikidata_ids: The identifiers for entities to query
    :param prefix_to_wikidata: A mapping from prefix to Wikidata property

    :returns: A dict from identifier to set of property-mediated semantic mappings
    """
    rv: defaultdict[str, set[curies.Reference]] = defaultdict(set)
    for prefix, wikidata_property_id in prefix_to_wikidata.items():
        if wikidata_property_id is None:
            continue
        properties = wikidata_client.get_properties(
            wikidata_ids, wikidata_property_id, single_value=False
        )
        for wikidata_id, external_ids in properties.items():
            for external_id in external_ids:
                rv[wikidata_id].add(curies.Reference(prefix=prefix, identifier=external_id))
    return dict(rv)


#: P2888 is "exact match", see https://www.wikidata.org/wiki/Property:P2888
WIKIDATA_EXACT_MATCH_PROP = "P2888"


def get_exact_matches_by_ids(
    wikidata_ids: Collection[str], *, converter: Converter | None = None
) -> dict[str, set[curies.Reference]]:
    """Get exact matches from Wikidata for the given entities.

    :param wikidata_ids: The identifiers for entities to query
    :param converter: A converter for compressing the URIs

    :returns: A dict from identifier to set of exact match semantic mappings
    """
    converter = _ensure_converter(converter)
    res = wikidata_client.get_properties(
        wikidata_ids, WIKIDATA_EXACT_MATCH_PROP, single_value=False
    )
    return {
        wikidata_id: {
            reference.to_pydantic() for uri in uris if (reference := converter.parse(uri))
        }
        for wikidata_id, uris in res.items()
    }


def _ensure_converter(converter: Converter | None) -> Converter:
    if converter is not None:
        return converter
    import bioregistry

    return bioregistry.get_default_converter()
