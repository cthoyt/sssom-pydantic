"""Convert semantic mappings into JSKOS format."""

import curies
from jskos import Concept, ProcessedConcept

from sssom_pydantic import SemanticMapping


def mapping_to_jskos(mapping: SemanticMapping, converter: curies.Converter) -> Concept:
    """"""
    processed_skos = mapping_to_processed_jskos(mapping)
    # TODO need to update JSKOS to have an "unprocess" function,
    #  https://github.com/biopragmatics/curies/pull/203


def mapping_to_processed_jskos(mapping: SemanticMapping) -> ProcessedConcept:
    """Get a processed concept."""
    raise NotImplementedError
