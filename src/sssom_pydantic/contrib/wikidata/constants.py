"""Constants for Wikidata."""

from __future__ import annotations

import curies
from curies import vocabulary as cv

__all__ = [
    "SKOS_TO_WIKIDATA",
    "WIKIDATA_PROPERTY_TO_PREDICATE",
    "WIKIDATA_TO_SKOS",
]

#: A mapping from SKOS references to Wikidata entities
SKOS_TO_WIKIDATA: dict[curies.Reference, str] = {
    cv.exact_match: "Q39893449",  # see https://www.wikidata.org/wiki/Q39893449
    cv.related_match: "Q39894604",  # see https://www.wikidata.org/wiki/Q39894604
    cv.close_match: "Q39893184",  # see https://www.wikidata.org/wiki/Q39893184
    cv.narrow_match: "Q39893967",  # see https://www.wikidata.org/wiki/Q39893967
    cv.broad_match: "Q39894595",  # see https://www.wikidata.org/wiki/Q39894595
}
#: A mapping from Wikidata entities to SKOS references
WIKIDATA_TO_SKOS = {v: k for k, v in SKOS_TO_WIKIDATA.items()}

#: P1628 is "equivalent property", see https://www.wikidata.org/wiki/Property:P1628,
#: exactly same as owl:equivalentProperty
EQUIVALENT_PROPERTY_PID = "P1628"

#: equivalent class - https://www.wikidata.org/wiki/Property:P1709,
#: exactly same as owl:equivalentClass
EQUIVALENT_CLASS_PID = "P1709"

#: P2888 is "exact match", see https://www.wikidata.org/wiki/Property:P2888,
#: exactly same as skos:exactMatch
EXACT_MATCH_PID = "P2888"

#: narrower external class - https://www.wikidata.org/wiki/Property:P3950,
#: exactly same as skos:narrowMatch
NARROWER_EXTERNAL_CLASS_PID = "P3950"

#: broader concept - https://www.wikidata.org/wiki/Property:P4900,
#: exactly same as skos:broadMatch
BROADER_CONCEPT_PID = "P4900"

#: external superproperty - https://www.wikidata.org/wiki/Property:P2235,
#: subproperty of rdfs:subPropertyOf (very meta)
EXTERNAL_SUPERPROPERTY_PID = "P2235"

#: A mapping from Wikidata property IDs to predicate references
WIKIDATA_PROPERTY_TO_PREDICATE = {
    # owl-like properties
    EQUIVALENT_PROPERTY_PID: cv.equivalent_property,
    EQUIVALENT_CLASS_PID: cv.equivalent_class,
    EXTERNAL_SUPERPROPERTY_PID: cv.subproperty_of,
    # skos-like properties
    EXACT_MATCH_PID: cv.exact_match,
    NARROWER_EXTERNAL_CLASS_PID: cv.narrow_match,
    BROADER_CONCEPT_PID: cv.broad_match,
}
