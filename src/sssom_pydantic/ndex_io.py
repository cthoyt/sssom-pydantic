"""Convert mappings into CX."""

from __future__ import annotations

from typing import TYPE_CHECKING

import curies
from tqdm import tqdm

from .api import MappingSet, SemanticMapping

if TYPE_CHECKING:
    import ndex2

__all__ = [
    "get_cx",
    "get_cx_builder",
]


def get_cx(
    mappings: list[SemanticMapping],
    metadata: MappingSet,
    *,
    converter: curies.Converter | None = None,
) -> ndex2.NiceCXNetwork:
    """Get a CX network."""
    cx = get_cx_builder(mappings, metadata, converter=converter)
    nice_cx = cx.get_nice_cx()
    return nice_cx


def get_cx_builder(
    mappings: list[SemanticMapping],
    metadata: MappingSet,
    *,
    converter: curies.Converter | None = None,
) -> ndex2.NiceCXBuilder:
    """Get a CX builder."""
    try:
        from ndex2 import NiceCXBuilder
    except ImportError as e:
        raise ImportError("Need to `pip install ndex2` before uploading to NDEx") from e
    builder = NiceCXBuilder()
    builder.add_network_attribute("reference", metadata.mapping_set_id)
    if metadata.mapping_set_title:
        builder.set_name(metadata.mapping_set_title)
    if metadata.mapping_set_description:
        builder.add_network_attribute("description", metadata.mapping_set_description)
    if metadata.license:
        builder.add_network_attribute("rights", metadata.license)
    if metadata.mapping_set_version:
        builder.add_network_attribute("version", metadata.mapping_set_version)

    if converter is None:
        import bioregistry

        prefixes: set[str] = {prefix for mapping in mappings for prefix in mapping.get_prefixes()}
        # TODO is there a better version of this?
        prefix_map = {prefix: bioregistry.get_uri_prefix(prefix) for prefix in prefixes}
    else:
        prefix_map = converter.bimap

    builder.set_context(prefix_map)

    author_orcid_ids = sorted(
        {
            mapping.author.identifier
            for mapping in mappings
            if mapping.author and mapping.author.prefix == "orcid"
        }
    )
    builder.add_network_attribute("author", author_orcid_ids, type="list_of_string")

    for mapping in tqdm(mappings, desc="Loading NiceCXBuilder"):
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
