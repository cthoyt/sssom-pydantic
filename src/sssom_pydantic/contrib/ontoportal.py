"""Get mappings from an OntoPortal instance.

.. code-block:: python

    import bioregistry
    from sssom_pydantic.contrib.ontoportal import from_bioportal

    converter = bioregistry.get_converter()
    mappings = from_bioportal("SNOMEDCT", "AERO", converter=converter)
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
    ontology_1: str,
    ontology_2: str,
    *,
    converter: curies.Converter,
    client: ontoportal_client.BioPortalClient | None = None,
) -> list[SemanticMapping]:
    """Get mappings from BioPortal.

    :param ontology_1: The OntoPortal instance's key for the first ontology. Note that
        this might not be the standard key/prefix, e.g., that's in the Bioregistry.
    :param ontology_2: The OntoPortal instance's key for the second ontology. Note that
        this might not be the standard key/prefix, e.g., that's in the Bioregistry.
    :param converter: A converter for parsing URIs
    :param client: A pre-instantiated BioPortal client. If not given, will try to
        automatically construct one. Note that this requires having an API key
        configured.

    :returns: A list of semantic mappings.

        .. warning::

            BioPortal doesn't provide an option to only return mappings between entities
            defined in the two given ontologies. For example, if you ask for mappings
            between ``SNOMEDCT`` and ``AERO``, you will also get mappings between OGMS
            and SNOMEDCT (because OGMS terms are imported in AERO).

            This means that you should probably apply post-hoc filtering to only retain
            relevant mappings.


    Simple usage:

    .. code-block:: python

        import bioregistry
        from sssom_pydantic.contrib.ontoportal import from_bioportal

        converter = bioregistry.get_converter()
        mappings = from_bioportal("SNOMEDCT", "AERO", converter=converter)

    Usage with explicitly defined converter, which implicitly filters only to relevant
    mappings:

    .. code-block:: python

        import curies
        from sssom_pydantic.contrib.ontoportal import from_bioportal

        converter = curies.Converter.from_prefix_map(
            {
                "AERO": "http://purl.obolibrary.org/obo/AERO_",
                "SNOMEDCT": "http://purl.bioontology.org/ontology/SNOMEDCT/",
            }
        )
        mappings = from_bioportal("SNOMEDCT", "AERO", converter=converter)
    """
    if client is None:
        from ontoportal_client import BioPortalClient

        client = BioPortalClient()
    return from_ontoportal(ontology_1, ontology_2, client=client, converter=converter)


def from_ontoportal(
    ontology_1: str,
    ontology_2: str,
    *,
    converter: curies.Converter,
    client: ontoportal_client.Client,
) -> list[SemanticMapping]:
    """Get mappings from an OntoPortal instance.

    :param ontology_1: The OntoPortal instance's key for the first ontology. Note that
        this might not be the standard key/prefix, e.g., that's in the Bioregistry.
    :param ontology_2: The OntoPortal instance's key for the second ontology. Note that
        this might not be the standard key/prefix, e.g., that's in the Bioregistry.
    :param converter: A converter for parsing URIs.

        Because OntoPortal's mapping data model does not incorporate a prefix map, an
        explicit converter must be passed to this function. The Bioregistry's default
        converter is sometimes a good option to put here if you're not sure (returned by
        :func:`bioregistry.get_converter`), but OntoPortal instances tend to make their
        own PURLs that might not be known to the Bioregistry.
    :param client: A pre-instantiated OntoPortal client, e.g., to BioPortal, AgroPortal,
        EcoPortal, etc.

    :returns: A list of semantic mappings.

        .. warning::

            OntoPortal doesn't provide an option to only return mappings between
            entities defined in the two given ontologies. For example, if you ask for
            mappings between ``SNOMEDCT`` and ``AERO`` in BioPortal, you will also get
            mappings between OGMS and SNOMEDCT (because OGMS terms are imported in
            AERO).

            This means that you should probably apply post-hoc filtering to only retain
            relevant mappings.


    Simple usage:

    .. code-block:: python

        import bioregistry
        from ontoportal_client import BioPortalClient
        from sssom_pydantic.contrib.ontoportal import from_ontoportal

        converter = bioregistry.get_converter()
        client = BioPortalClient()
        mappings = from_ontoportal("SNOMEDCT", "AERO", converter=converter, client=client)

    Usage with explicitly defined converter, which implicitly filters only to relevant
    mappings:

    .. code-block:: python

        import curies
        from ontoportal_client import BioPortalClient
        from sssom_pydantic.contrib.ontoportal import from_ontoportal

        converter = curies.Converter.from_prefix_map(
            {
                "AERO": "http://purl.obolibrary.org/obo/AERO_",
                "SNOMEDCT": "http://purl.bioontology.org/ontology/SNOMEDCT/",
            }
        )
        client = BioPortalClient()
        mappings = from_bioportal("SNOMEDCT", "AERO", converter=converter, client=client)
    """
    rv = []
    for data in client.get_mappings(ontology_1, ontology_2):
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
