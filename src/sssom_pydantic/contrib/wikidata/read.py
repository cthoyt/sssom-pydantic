"""Read operations for Wikidata."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Collection, Iterable
from textwrap import dedent
from typing import Unpack

import curies
import wikidata_client
from curies import Converter, NamableReference
from curies import vocabulary as cv
from tqdm import tqdm
from wikidata_client import QueryKwargs

from sssom_pydantic import SemanticMapping
from sssom_pydantic.constants import CC0_URL

from .constants import WIKIDATA_TO_SKOS

__all__ = [
    "EQUIVALENT_PROPERTY_SPARQL",
    "get_equivalent_property_mappings",
    "get_exact_match_mappings",
    "get_exact_matches_by_ids",
    "get_mappings_by_property",
    "get_property_matches_by_ids",
]

#: A wikidata entry about itself
WIKIDATA_SOURCE_R = NamableReference(prefix="wikidata", identifier="Q2013", name="Wikidata")

#: P1628 is "equivalent property", see https://www.wikidata.org/wiki/Property:P1628
EQUIVALENT_PROPERTY_PID = "P1628"

#: The SPARQL query for returning all `equivalent properties <https://www.wikidata.org/wiki/Property:P1628>`_
EQUIVALENT_PROPERTY_SPARQL = """\
    SELECT ?item ?itemLabel ?uri ?mappingType
    WHERE {
        ?item p:P1628 ?statement .
        ?statement ps:P1628 ?uri .
        OPTIONAL { ?statement pq:P4390 ?mappingType }
        SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],mul,en" . }
    }
"""

#: P2888 is "exact match", see https://www.wikidata.org/wiki/Property:P2888
EXACT_MATCH_PID = "P2888"

EXACT_MATCH_SPARQL = """
    SELECT ?item ?itemLabel ?uri ?mappingType
    WHERE {
        ?item p:P2888 ?statement .
        ?statement ps:P2888 ?uri .
        OPTIONAL { ?statement pq:P4390 ?mappingType }
        SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],mul,en" . }
    }
"""


def get_equivalent_property_mappings(
    *,
    converter: Converter | None = None,
    **kwargs: Unpack[QueryKwargs],
) -> list[SemanticMapping]:
    """Get mappings from Wikidata encoded in "equivalent property" triples.

    :param converter: A converter for parsing the URIs of the objects of equivalent
        property triples.
    :param kwargs: SPARQL query keyword arguments passed to :func:`wikidata_client.query`

    :returns: A list of semantic mappings

    .. note::

        In September 2026, there were 861 results, with 4 that included mapping types.
    """
    return list(
        _get_mapping_to_uri(converter, EQUIVALENT_PROPERTY_SPARQL, cv.equivalent_property, **kwargs)
    )


def get_exact_match_mappings(
    *,
    converter: Converter | None = None,
    **kwargs: Unpack[QueryKwargs],
) -> list[SemanticMapping]:
    """Get mappings from Wikidata encoded in "exact match" triples.

    :param converter: A converter for parsing the URIs of the objects of equivalent
        property triples.
    :param kwargs: SPARQL query keyword arguments passed to :func:`wikidata_client.query`

    :returns: A list of semantic mappings

    .. note::

        In September 2026, there were on the scale of 500K results
    """
    return list(_get_mapping_to_uri(converter, EXACT_MATCH_SPARQL, cv.exact_match, **kwargs))


def _get_mapping_to_uri(
    converter: Converter | None,
    sparql: str,
    default_pred: curies.Reference,
    **kwargs: Unpack[QueryKwargs],
) -> Iterable[SemanticMapping]:
    converter = _ensure_converter(converter)
    for row in wikidata_client.query(sparql, **kwargs):
        object_uri = row["uri"]
        object_reference_tuple = converter.parse_uri(object_uri)
        if object_reference_tuple is None:
            tqdm.write(f"failed to parse object URI: {object_uri}")
            continue
        yield SemanticMapping(
            subject=NamableReference(
                prefix="wikidata", identifier=row["item"], name=row["itemLabel"]
            ),
            predicate=_handle_mapping_type(row.get("mappingType"), default_pred),
            object=object_reference_tuple.to_pydantic(),
            justification=cv.unspecified_matching_process,
            license=CC0_URL,
            source=WIKIDATA_SOURCE_R,
        )


def _handle_mapping_type(
    mapping_predicate_qid: str | None, default: curies.Reference
) -> curies.Reference:
    if mapping_predicate_qid is None:
        return default
    return WIKIDATA_TO_SKOS.get(mapping_predicate_qid, default)


def _get_mapping_sparql(property_id: str) -> str:
    """Get a SPARQL query for retrieving mappings with a given property.

    :param property_id: The property to retrieve, such as ``P683`` for ChEBI

    :returns: A SPARQL query
    """
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
    property_id: str,
    *,
    prefix: str | None = None,
    confidence: float | None = None,
    **kwargs: Unpack[QueryKwargs],
) -> Iterable[SemanticMapping]:
    """Yield mappings from Wikidata from the given property.

    :param property_id: The property to retrieve, such as ``P683`` for ChEBI
    :param prefix: The prefix to use when constructing references for the property,
        e.g., ``CHEBI`` for property `P683``. If not given, will look up using
        :mod:`bioregistry`.
    :param confidence: An optional confidence to apply to all mappings. Alternatively,
        confidence can be applied at the mapping set level
    :param kwargs: SPARQL query keyword arguments passed to :func:`wikidata_client.query`

    :yields: semantic mappings
    """
    if prefix is None:
        import bioregistry

        # todo use bioregistry.lookup_from
        prefix = bioregistry.get_registry_invmap("wikidata")[property_id]

    for row in wikidata_client.query(_get_mapping_sparql(property_id), **kwargs):
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
    prefix_to_wikidata: dict[str, str | None],  # TODO change this to properties list
    **kwargs: Unpack[QueryKwargs],
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
            wikidata_ids, wikidata_property_id, single_value=False, **kwargs
        )
        for wikidata_id, external_ids in properties.items():
            for external_id in external_ids:
                rv[wikidata_id].add(curies.Reference(prefix=prefix, identifier=external_id))
    return dict(rv)


def get_exact_matches_by_ids(
    wikidata_ids: Collection[str],
    *,
    converter: Converter | None = None,
    **kwargs: Unpack[QueryKwargs],
) -> dict[str, set[curies.Reference]]:
    """Get exact matches from Wikidata for the given entities.

    :param wikidata_ids: The identifiers for entities to query
    :param converter: A converter for compressing the URIs
    :param kwargs: SPARQL query keyword arguments passed to :func:`wikidata_client.query`

    :returns: A dict from identifier to set of exact match semantic mappings
    """
    converter = _ensure_converter(converter)
    res = wikidata_client.get_properties(
        wikidata_ids, EXACT_MATCH_PID, single_value=False, **kwargs
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
