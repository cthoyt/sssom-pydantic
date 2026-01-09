"""Convert mappings into CX."""

from __future__ import annotations

from typing import TYPE_CHECKING

import curies
import pystow

from ..api import MappingSet, SemanticMapping

if TYPE_CHECKING:
    import ndex2

__all__ = [
    "get_nice_cx",
    "get_nice_cx_builder",
    "update_ndex",
]

DEFAULT_SERVER = "http://public.ndexbio.org"


def update_ndex(
    uuid: str,
    mappings: list[SemanticMapping],
    *,
    metadata: MappingSet | None = None,
    converter: curies.Converter | None = None,
    server: str | None = None,
    username: str | None = None,
    password: str | None = None,
) -> None:
    """Update an existing graph on NDEx."""
    nice_cx = get_nice_cx(mappings, metadata=metadata, converter=converter)
    # TODO could return what this returns, but not sure what type it is
    nice_cx.update_to(
        uuid=uuid,
        server=pystow.get_config("ndex", "server", passthrough=server, default=DEFAULT_SERVER),
        username=pystow.get_config("ndex", "username", passthrough=username),
        password=pystow.get_config("ndex", "password", passthrough=password),
    )


def get_nice_cx(
    mappings: list[SemanticMapping],
    *,
    metadata: MappingSet | None = None,
    converter: curies.Converter | None = None,
) -> ndex2.NiceCXNetwork:
    """Get a nice CX network."""
    cx = get_nice_cx_builder(mappings, metadata=metadata, converter=converter)
    nice_cx = cx.get_nice_cx()
    return nice_cx


def get_nice_cx_builder(
    mappings: list[SemanticMapping],
    *,
    metadata: MappingSet | None = None,
    converter: curies.Converter | None = None,
) -> ndex2.NiceCXBuilder:
    """Get a nice CX builder."""
    try:
        from ndex2 import NiceCXBuilder
    except ImportError as e:
        raise ImportError("Need to `pip install ndex2` before uploading to NDEx") from e

    builder = NiceCXBuilder()
    builder.set_context(_get_prefix_map(mappings, converter=converter))

    if metadata is not None:
        builder.add_network_attribute("reference", metadata.id)
        if metadata.title:
            builder.set_name(metadata.title)
        if metadata.description:
            builder.add_network_attribute("description", metadata.description)
        if metadata.license:
            builder.add_network_attribute("rights", metadata.license)
        if metadata.version:
            builder.add_network_attribute("version", metadata.version)
        if metadata.creators:
            builder.add_network_attribute(
                "author", [a.curie for a in metadata.creators], type="list_of_string"
            )

    for mapping in mappings:
        source = builder.add_node(
            represents=mapping.subject_name,
            name=mapping.subject.curie,
        )
        target = builder.add_node(
            represents=mapping.object_name,
            name=mapping.object.curie,
        )
        edge = builder.add_edge(
            source=source,
            target=target,
            interaction=mapping.predicate.curie,
        )
        builder.add_edge_attribute(edge, "mapping_justification", mapping.justification.curie)
        if mapping.authors:
            builder.add_edge_attribute(
                edge, "author_id", [a.curie for a in mapping.authors], type="list_of_string"
            )

    return builder


def _get_prefix_map(
    mappings: list[SemanticMapping], converter: curies.Converter | None = None
) -> dict[str, str]:
    if converter is not None:
        return dict(converter.bimap)

    try:
        import bioregistry
    except ImportError as e:
        raise ImportError(
            "no converter was given. tried falling back to look up URI prefixes "
            "with the Bioregistry, but it's not installed. Install using "
            "`pip install bioregistry`"
        ) from e

    prefixes: set[str] = {prefix for mapping in mappings for prefix in mapping.get_prefixes()}
    # TODO is there a better version of this?
    return {
        prefix: uri_prefix
        for prefix in prefixes
        if (uri_prefix := bioregistry.get_uri_prefix(prefix))
    }
