"""Read operations for Wikidata."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from textwrap import dedent
from typing import Unpack

import bioregistry
import curies
import wikidata_client
from curies import Converter, NamableReference
from curies import vocabulary as cv
from tqdm import tqdm
from wikidata_client import QueryKwargs

from .constants import (
    BROADER_CONCEPT_PID,
    EQUIVALENT_CLASS_PID,
    EQUIVALENT_PROPERTY_PID,
    EXACT_MATCH_PID,
    EXTERNAL_SUPERPROPERTY_PID,
    NARROWER_EXTERNAL_CLASS_PID,
    WIKIDATA_PROPERTY_TO_PREDICATE,
    WIKIDATA_TO_SKOS,
)
from ...api import SemanticMapping
from ...constants import CC0_URL

__all__ = [
    "EQUIVALENT_PROPERTY_SPARQL",
    "EXACT_MATCH_SPARQL",
    "get_broad_match_mappings",
    "get_equivalent_class_mappings",
    "get_equivalent_properties_by_ids",
    "get_equivalent_property_mappings",
    "get_exact_match_mappings",
    "get_exact_matches_by_ids",
    "get_mappings",
    "get_mappings_by_prefix",
    "get_mappings_by_property",
    "get_mappings_by_property_sparql",
    "get_narrow_match_mappings",
    "get_property_mappings",
    "get_property_matches_by_ids",
    "get_subproperty_of_mappings",
    "get_uri_mappings",
    "get_uri_mappings_sparql",
]

#: A wikidata entry about itself
WIKIDATA_SOURCE_R = NamableReference(prefix="wikidata", identifier="Q2013", name="Wikidata")


def get_equivalent_property_mappings(
    *,
    converter: Converter | None = None,
    confidence: float | None = None,
    **kwargs: Unpack[QueryKwargs],
) -> list[SemanticMapping]:
    """Get mappings from Wikidata encoded in "equivalent property" triples.

    :param converter: A converter for parsing the URIs of the objects of equivalent
        property triples.
    :param confidence: An optional confidence to apply to all mappings
    :param kwargs: SPARQL query keyword arguments passed to
        :func:`wikidata_client.query`

    :returns: A list of semantic mappings

    .. note::

        In September 2026, there were 861 results, with 4 that included mapping types.
    """
    return list(
        _get_mapping_to_uri(
            EQUIVALENT_PROPERTY_PID, converter=converter, confidence=confidence, **kwargs
        )
    )


def get_equivalent_class_mappings(
    *,
    converter: Converter | None = None,
    confidence: float | None = None,
    **kwargs: Unpack[QueryKwargs],
) -> list[SemanticMapping]:
    """Get mappings from Wikidata encoded in "equivalent class" triples.

    :param converter: A converter for parsing the URIs of the objects of equivalent
        property triples.
    :param confidence: An optional confidence to apply to all mappings
    :param kwargs: SPARQL query keyword arguments passed to
        :func:`wikidata_client.query`

    :returns: A list of semantic mappings
    """
    return list(
        _get_mapping_to_uri(
            EQUIVALENT_CLASS_PID, converter=converter, confidence=confidence, **kwargs
        )
    )


def get_subproperty_of_mappings(
    *,
    converter: Converter | None = None,
    confidence: float | None = None,
    **kwargs: Unpack[QueryKwargs],
) -> list[SemanticMapping]:
    """Get mappings from Wikidata encoded in "external superproperty" triples.

    :param converter: A converter for parsing the URIs of the objects of equivalent
        property triples.
    :param confidence: An optional confidence to apply to all mappings
    :param kwargs: SPARQL query keyword arguments passed to
        :func:`wikidata_client.query`

    :returns: A list of semantic mappings
    """
    return list(
        _get_mapping_to_uri(
            EXTERNAL_SUPERPROPERTY_PID, converter=converter, confidence=confidence, **kwargs
        )
    )


def get_exact_match_mappings(
    *,
    converter: Converter | None = None,
    confidence: float | None = None,
    **kwargs: Unpack[QueryKwargs],
) -> list[SemanticMapping]:
    """Get mappings from Wikidata encoded in "exact match" triples.

    :param converter: A converter for parsing the URIs of the objects of equivalent
        property triples.
    :param confidence: An optional confidence to apply to all mappings
    :param kwargs: SPARQL query keyword arguments passed to
        :func:`wikidata_client.query`

    :returns: A list of semantic mappings

    .. note::

        In September 2026, there were on the scale of 500K results
    """
    return list(
        _get_mapping_to_uri(EXACT_MATCH_PID, converter=converter, confidence=confidence, **kwargs)
    )


def get_narrow_match_mappings(
    *,
    converter: Converter | None = None,
    confidence: float | None = None,
    **kwargs: Unpack[QueryKwargs],
) -> list[SemanticMapping]:
    """Get mappings from Wikidata encoded in "narrow match" triples.

    :param converter: A converter for parsing the URIs of the objects of equivalent
        property triples.
    :param confidence: An optional confidence to apply to all mappings
    :param kwargs: SPARQL query keyword arguments passed to
        :func:`wikidata_client.query`

    :returns: A list of semantic mappings
    """
    return list(
        _get_mapping_to_uri(
            NARROWER_EXTERNAL_CLASS_PID, converter=converter, confidence=confidence, **kwargs
        )
    )


def get_broad_match_mappings(
    *,
    converter: Converter | None = None,
    confidence: float | None = None,
    **kwargs: Unpack[QueryKwargs],
) -> list[SemanticMapping]:
    """Get mappings from Wikidata encoded in "broad match" triples.

    :param converter: A converter for parsing the URIs of the objects of equivalent
        property triples.
    :param confidence: An optional confidence to apply to all mappings
    :param kwargs: SPARQL query keyword arguments passed to
        :func:`wikidata_client.query`

    :returns: A list of semantic mappings
    """
    return list(
        _get_mapping_to_uri(
            BROADER_CONCEPT_PID, converter=converter, confidence=confidence, **kwargs
        )
    )


def get_uri_mappings(
    *,
    converter: Converter | None = None,
    confidence: float | None = None,
    **kwargs: Unpack[QueryKwargs],
) -> Iterable[SemanticMapping]:
    """Get all URI-based mappings from Wikidata.

    :param converter: A converter for parsing the URIs of the objects of equivalent
        property triples.
    :param confidence: An optional confidence to apply to all mappings
    :param kwargs: SPARQL query keyword arguments passed to
        :func:`wikidata_client.query`

    :returns: A list of semantic mappings

    .. note::

        this subsumes :func:`get_exact_match_mappings` and
        :func:`get_equivalent_property_mappings`, and all other functions build on top
        of :data:`WIKIDATA_PROPERTY_TO_PREDICATE`.
    """
    for wikidata_property in WIKIDATA_PROPERTY_TO_PREDICATE:
        yield from _get_mapping_to_uri(
            wikidata_property, converter=converter, confidence=confidence, **kwargs
        )


def get_uri_mappings_sparql(wikidata_property: str) -> str:
    """Get the SPARQL query for a given Wikidata property."""
    return dedent(f"""\
        SELECT ?item ?itemLabel ?uri ?mappingType
        WHERE {{
            ?item p:{wikidata_property} ?statement .
            ?statement ps:{wikidata_property} ?uri .
            OPTIONAL {{ ?statement pq:P4390 ?mappingType }}
            SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],mul,en" }}
        }}
    """)


#: The SPARQL query for returning all `equivalent properties <https://www.wikidata.org/wiki/Property:P1628>`_
EQUIVALENT_PROPERTY_SPARQL = get_uri_mappings_sparql(EQUIVALENT_PROPERTY_PID)

#: The SPARQL query for returning all `exact matches <https://www.wikidata.org/wiki/Property:P2888>`_
EXACT_MATCH_SPARQL = get_uri_mappings_sparql(EXACT_MATCH_PID)


def _get_mapping_to_uri(
    wikidata_property: str,
    *,
    converter: Converter | None = None,
    confidence: float | None,
    **kwargs: Unpack[QueryKwargs],
) -> Iterable[SemanticMapping]:
    sparql = get_uri_mappings_sparql(wikidata_property)
    default_predicate = WIKIDATA_PROPERTY_TO_PREDICATE[wikidata_property]
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
            predicate=_handle_mapping_type(row.get("mappingType"), default_predicate),
            object=object_reference_tuple.to_pydantic(),
            justification=cv.unspecified_matching_process,
            license=CC0_URL,
            source=WIKIDATA_SOURCE_R,
            confidence=confidence,
        )


def _handle_mapping_type(
    mapping_predicate_qid: str | None, default: curies.Reference
) -> curies.Reference:
    if mapping_predicate_qid is None:
        return default
    return WIKIDATA_TO_SKOS.get(mapping_predicate_qid, default)


def get_mappings_by_property_sparql(property_id: str) -> str:
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


def get_mappings_by_prefix(
    prefix: str,
    *,
    property_id: str | None = None,
    confidence: float | None = None,
    **kwargs: Unpack[QueryKwargs],
) -> Iterable[SemanticMapping]:
    """Yield mappings from Wikidata from the given property.

    :param prefix: The prefix to use when constructing references for the property,
        e.g., ``CHEBI`` for property `P683``.
    :param property_id: The property to retrieve, such as ``P683`` for ChEBI. If not
        given, will look up using :mod:`bioregistry`.
    :param confidence: An optional confidence to apply to all mappings
    :param kwargs: SPARQL query keyword arguments passed to
        :func:`wikidata_client.query`

    :yields: semantic mappings
    """
    if property_id is None:
        import bioregistry

        property_id = bioregistry.get_registry_map(prefix)["wikidata.property"]
    yield from _get_mappings_by_property_helper(
        prefix=prefix, property_id=property_id, confidence=confidence, **kwargs
    )


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
    :param confidence: An optional confidence to apply to all mappings
    :param kwargs: SPARQL query keyword arguments passed to
        :func:`wikidata_client.query`

    :yields: semantic mappings
    """
    if prefix is None:
        import bioregistry

        # todo use bioregistry.lookup_from
        prefix = bioregistry.get_registry_invmap("wikidata.property")[property_id]
    yield from _get_mappings_by_property_helper(
        prefix=prefix, property_id=property_id, confidence=confidence, **kwargs
    )


def _get_mappings_by_property_helper(
    *,
    prefix: str,
    property_id: str,
    confidence: float | None = None,
    **kwargs: Unpack[QueryKwargs],
) -> Iterable[SemanticMapping]:
    from ...api import SemanticMapping

    for row in wikidata_client.query(get_mappings_by_property_sparql(property_id), **kwargs):
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
    wikidata_ids: Iterable[str],
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
    wikidata_ids: Iterable[str],
    *,
    converter: Converter | None = None,
    **kwargs: Unpack[QueryKwargs],
) -> dict[str, set[curies.Reference]]:
    """Get exact matches from Wikidata for the given entities.

    :param wikidata_ids: The identifiers for entities to query
    :param converter: A converter for compressing the URIs
    :param kwargs: SPARQL query keyword arguments passed to
        :func:`wikidata_client.query`

    :returns: A dict from identifier to set of exact match semantic mappings
    """
    return _get_uri_matches_by_ids(wikidata_ids, EXACT_MATCH_PID, converter=converter, **kwargs)


def get_equivalent_properties_by_ids(
    wikidata_ids: Iterable[str],
    *,
    converter: Converter | None = None,
    **kwargs: Unpack[QueryKwargs],
) -> dict[str, set[curies.Reference]]:
    """Get equivalent properties from Wikidata for the given entities.

    :param wikidata_ids: The identifiers for entities to query
    :param converter: A converter for compressing the URIs
    :param kwargs: SPARQL query keyword arguments passed to
        :func:`wikidata_client.query`

    :returns: A dict from identifier to set of exact match semantic mappings
    """
    return _get_uri_matches_by_ids(
        wikidata_ids, EQUIVALENT_PROPERTY_PID, converter=converter, **kwargs
    )


def _get_uri_matches_by_ids(
    wikidata_ids: Iterable[str],
    prop: str,
    *,
    converter: Converter | None,
    **kwargs: Unpack[QueryKwargs],
) -> dict[str, set[curies.Reference]]:
    converter = _ensure_converter(converter)
    res = wikidata_client.get_properties(wikidata_ids, prop, single_value=False, **kwargs)
    return {
        wikidata_id: {
            reference.to_pydantic() for uri in uris if (reference := converter.parse(uri))
        }
        for wikidata_id, uris in res.items()
    }


def get_property_mappings(
    *, confidence: float | None = None, **kwargs: Unpack[QueryKwargs]
) -> Iterable[SemanticMapping]:
    """Iterate over all property-based mappings.

    :param confidence: An optional confidence to apply to all mappings
    :param kwargs: SPARQL query keyword arguments passed to
        :func:`wikidata_client.query`

    :yields: semantic mappings

    .. note::

        if you only want mappings for one property, use :func:`get_mappings_by_property`
    """
    import bioregistry

    for prefix, property_id in bioregistry.get_registry_invmap("wikidata.property").items():
        yield from _get_mappings_by_property_helper(
            prefix=prefix, property_id=property_id, confidence=confidence, **kwargs
        )


def get_mappings(
    *,
    converter: Converter | None = None,
    confidence: float | None = None,
    **kwargs: Unpack[QueryKwargs],
) -> Iterable[SemanticMapping]:
    """Iterate over all mappings from Wikidata.

    :param converter: A converter for parsing the URIs of the objects of equivalent
        property triples.
    :param confidence: An optional confidence to apply to all mappings
    :param kwargs: SPARQL query keyword arguments passed to
        :func:`wikidata_client.query`
    """
    yield from get_property_mappings(confidence=confidence, **kwargs)
    yield from get_uri_mappings(converter=converter, confidence=confidence, **kwargs)


def _ensure_converter(converter: Converter | None) -> Converter:
    if converter is not None:
        return converter

    return bioregistry.get_default_converter()
