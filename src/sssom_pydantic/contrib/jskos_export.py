"""Convert semantic mappings into JSKOS format."""

from functools import partial

import curies
import jskos
from jskos import Concept

from sssom_pydantic import MappingSet, SemanticMapping

__all__ = [
    "mapping_set_to_jskos",
    "mapping_to_jskos",
]


def mapping_set_to_jskos(
    mappings: list[SemanticMapping], converter: curies.Converter, metadata: MappingSet
) -> Concept:
    """Convert a mapping set to JSKOS."""
    rv = Concept(
        identifier=[metadata.id],
        license=[Concept(uri=metadata.license)],
        mappings=[mapping_to_jskos(mapping, converter) for mapping in mappings],
    )
    return rv


def mapping_to_jskos(mapping: SemanticMapping, converter: curies.Converter) -> jskos.Mapping:
    """Convert a mapping to JSKOS."""
    _r = partial(converter.expand_reference, strict=True)

    return jskos.Mapping.model_validate(
        {
            "type": [_r(mapping.predicate)],
            "from": Concept(member_set=[Concept(uri=_r(mapping.subject))]),
            "to": Concept(member_set=[Concept(uri=_r(mapping.object))]),
            "justification": _r(mapping.justification),
        }
    )
