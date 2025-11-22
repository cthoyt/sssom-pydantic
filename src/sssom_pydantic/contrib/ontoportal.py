"""Get mappings from OntoPortal."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import curies
from curies import Reference
from curies.vocabulary import has_dbxref, lexical_matching_process

from sssom_pydantic import MappingTool, SemanticMapping

if TYPE_CHECKING:
    import ontoportal_client

logger = logging.getLogger(__name__)


def from_bioportal(
    o1: str, o2: str, *, converter: curies.Converter | None = None
) -> list[SemanticMapping]:
    from ontoportal_client import BioPortalClient

    return from_ontoportal(o1, o2, client=BioPortalClient(), converter=converter)


def from_ontoportal(
    o1: str,
    o2: str,
    *,
    converter: curies.Converter | None = None,
    client: ontoportal_client.Client,
) -> list[SemanticMapping]:
    if converter is None:
        import bioregistry

        converter = bioregistry.get_converter()

    rv = []
    for data in client.get_mappings(o1, o2):
        if semantic_mapping := _process(data, converter=converter):
            rv.append(semantic_mapping)
    return rv


def _process(data: dict[str, Any], converter: curies.Converter) -> SemanticMapping | None:
    subject_raw, target_raw = data["classes"]
    subject = _process_class(subject_raw, converter)
    if subject is None:
        return None
    obj = _process_class(target_raw, converter)
    if obj is None:
        return None

    tool = data["source"]
    if tool == "LOOM":
        # see https://www.bioontology.org/wiki/LOOM
        mapping_tool = MappingTool(name="LOOM")
        justification = lexical_matching_process
    else:
        logger.warning("unhandled mapping tool: %s", tool)
        return None
    return SemanticMapping(
        subject=subject,
        predicate=has_dbxref,
        object=obj,
        justification=justification,
        mapping_tool=mapping_tool,
    )


def _process_class(data: dict[str, Any], converter: curies.Converter) -> Reference | None:
    uri = data["@id"]
    reference_tuple = converter.parse_uri(uri)
    if reference_tuple is None:
        logger.warning("could not parse: %s", uri)
        return None
    return reference_tuple.to_pydantic()


if __name__ == "__main__":
    from_bioportal("SNOMEDCT", "AERO")
