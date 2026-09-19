"""Constants for Wikidata."""

from __future__ import annotations

import curies
from curies import vocabulary as cv

__all__ = [
    "SKOS_TO_WIKIDATA",
    "WIKIDATA_TO_SKOS",
]

SKOS_TO_WIKIDATA: dict[curies.Reference, str] = {
    cv.exact_match: "Q39893449",  # see https://www.wikidata.org/wiki/Q39893449
    cv.related_match: "Q39894604",  # see https://www.wikidata.org/wiki/Q39894604
    cv.close_match: "Q39893184",  # see https://www.wikidata.org/wiki/Q39893184
    cv.narrow_match: "Q39893967",  # see https://www.wikidata.org/wiki/Q39893967
    cv.broad_match: "Q39894595",  # see https://www.wikidata.org/wiki/Q39894595
}
WIKIDATA_TO_SKOS = {v: k for k, v in SKOS_TO_WIKIDATA.items()}
