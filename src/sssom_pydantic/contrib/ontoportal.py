"""Get mappings from an OntoPortal instance.

.. code-block:: python

    from sssom_pydantic.contrib.ontoportal import from_bioportal

    mappings = from_bioportal("SNOMEDCT", "AERO")
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import curies
from curies import Reference
from curies.vocabulary import exact_match, lexical_matching_process

from sssom_pydantic import MappingTool, SemanticMapping

if TYPE_CHECKING:
    import ontoportal_client

logger = logging.getLogger(__name__)


def from_bioportal(
    o1: str,
    o2: str,
    *,
    converter: curies.Converter | None = None,
    client: ontoportal_client.BioPortalClient | None = None,
) -> list[SemanticMapping]:
    """Get mappings from BioPortal.

    :param o1: The first ontology
    :param o2: The second ontology
    :param client: A pre-instantiated BioPortal client. If not given, will try to
        automatically construct one. Note that this requires having an API key
        configured.
    :param converter: A converter for parsing URIs

    :returns: A list of semantic mappings.

    .. warning::

        BioPortal contains irrelevant mappings, i.e., ones that are made between
        imported terms. Therefore, you should check that the ontologies match the parsed
        results
    """
    if client is None:
        from ontoportal_client import BioPortalClient

        client = BioPortalClient()
    return from_ontoportal(o1, o2, client=client, converter=converter)


def from_ontoportal(
    o1: str,
    o2: str,
    *,
    converter: curies.Converter | None = None,
    client: ontoportal_client.Client,
) -> list[SemanticMapping]:
    """Get mappings from an OntoPortal instance.

    :param o1: The first ontology
    :param o2: The second ontology
    :param client: A pre-instantiated OntoPortal client, e.g., to BioPortal, AgroPortal,
        EcoPortal, etc.
    :param converter: A converter for parsing URIs

    :returns: A list of semantic mappings.

    .. warning::

        OntoPortal's mapping data model includes any mappings between terms that have
        been imported into the ontologies, meaning that you should filter post-facto to
        only keep mappings whose subject/object match the query ontologies.

        This isn't possible to do directly because OntoPortal's data model does not
        contain a prefix map nor information about the defining ontology for a term
    """
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
        predicate = exact_match
    else:
        logger.warning("unhandled mapping tool: %s", tool)
        return None
    return SemanticMapping(
        subject=subject,
        predicate=predicate,
        object=obj,
        justification=justification,
        mapping_tool=mapping_tool,
    )


def _process_class(data: dict[str, Any], converter: curies.Converter) -> Reference | None:
    uri = data["@id"]
    reference_tuple: curies.ReferenceTuple | None = converter.parse_uri(uri)
    if reference_tuple is None:
        logger.warning("could not parse: %s", uri)
        return None
    return reference_tuple.to_pydantic()
