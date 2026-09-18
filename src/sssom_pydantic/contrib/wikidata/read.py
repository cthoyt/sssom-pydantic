"""Read operations for Wikidata."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Collection, Iterable
from textwrap import dedent

import bioregistry
import curies
import wikidata_client
from curies import Converter, NamableReference
from curies import vocabulary as cv
from tqdm import tqdm

from sssom_pydantic import SemanticMapping
from sssom_pydantic.constants import CC0_URL

from .constants import WIKIDATA_TO_SKOS

__all__ = [
    "_get_wikidata_to_exact_matches",
    "_get_wikidata_to_property_matches",
    "get_mappings_by_prefix",
    "get_wikidata_property_mappings",
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


def get_wikidata_property_mappings(*, converter: Converter | None = None) -> list[SemanticMapping]:
    """Get equivalent properties from wikidata.

    In September 2026, there were 861 results, with 4 that included
    mapping types.
    """
    if converter is None:
        converter = bioregistry.get_default_converter()
    rv = []
    for row in wikidata_client.query(EQUIVALENT_PROPERTY_SPARQL):
        object_reference_tuple = converter.parse_uri(row["val"])
        if object_reference_tuple is None:
            tqdm.write(f"failed to parse {row['val']}")
            continue
        if mapping_predicate_qid := row.get("mappingType"):
            predicate = WIKIDATA_TO_SKOS.get(mapping_predicate_qid, cv.equivalent_property)
        else:
            predicate = cv.equivalent_property
        mapping = SemanticMapping(
            subject=NamableReference(
                prefix="wikidata", identifier=row["item"], name=row["itemLabel"]
            ),
            predicate=predicate,
            object=object_reference_tuple.to_pydantic(),
            justification=cv.unspecified_matching_process,
            license=CC0_URL,
            source=WIKIDATA_SOURCE_R,
        )
        rv.append(mapping)
    return rv


def get_mappings_by_prefix(
    *,
    prefix: str | None = None,
    property_id: str | None = None,
    confidence: float = 0.99,
    timeout: int = 300,
    endpoint: str | None = None,
) -> Iterable[SemanticMapping]:
    """Get mappings from Wikidata."""
    if prefix is None:
        if property_id is None:
            raise ValueError("must pass at least one of prefix or property_id")
        prefix = bioregistry.get_registry_invmap("wikidata")[property_id]
    elif property_id is None:
        property_id = bioregistry.get_registry_map("wikidata")[prefix]

    sparql = dedent(f"""\
        SELECT ?entity ?entityLabel ?id
        WHERE {{
            ?entity wdt:{property_id} ?id .
            SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],mul,en". }}
        }}
    """)
    # TODO extend to get match types?
    rows = wikidata_client.query(sparql, timeout=timeout, endpoint=endpoint)
    for row in rows:
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
            predicate=cv.exact_match,
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


def _get_wikidata_to_property_matches(
    wikidata_ids: Collection[str],
    prefix_to_wikidata: dict[str, str | None],
) -> dict[str, set[curies.Reference]]:
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


def _get_wikidata_to_exact_matches(
    wikidata_ids: Collection[str], converter: Converter
) -> dict[str, set[curies.Reference]]:
    # P2888 is "exact match", see https://www.wikidata.org/wiki/Property:P2888
    res = wikidata_client.get_properties(wikidata_ids, "P2888", single_value=False)
    return {
        wikidata_id: {
            reference.to_pydantic() for uri in uris if (reference := converter.parse(uri))
        }
        for wikidata_id, uris in res.items()
    }
