"""I/O for the :mod:`sssom` package."""

from __future__ import annotations

from typing import TYPE_CHECKING

import curies

from ..api import MappingSet, SemanticMapping
from ..io import Metadata, _safe_dump_mapping_set, _unprocess_row

if TYPE_CHECKING:
    import pandas
    import sssom

__all__ = [
    "to_sssompy",
]


def to_df(mappings: list[SemanticMapping]) -> pandas.DataFrame:
    """Construct a pandas dataframe that represents the SSSOM TSV format."""
    import pandas

    rows = [_unprocess_row(mapping.to_record()) for mapping in mappings]
    rv = pandas.DataFrame(rows)
    return rv


def to_sssompy(
    mappings: list[SemanticMapping],
    converter: curies.Converter,
    metadata: MappingSet | Metadata,
    *,
    linkml_validate: bool = False,
) -> sssom.MappingSetDataFrame:
    """Construct a SSSOM-py mapping set dataframe object."""
    from sssom import MappingSetDataFrame
    from sssom.parsers import from_sssom_dataframe

    df = to_df(mappings)
    meta = _safe_dump_mapping_set(metadata)
    meta["curie_map"] = converter.bimap
    if not linkml_validate:
        # we can trust that SSSOM-Pydantic makes a correct
        # dataframe, so we normally don't have to go through
        # the weird round-trip implemented in from_sssom_dataframe
        # through LinkML object I/O
        return MappingSetDataFrame(df=df, converter=converter, metadata=meta)

    return from_sssom_dataframe(
        df,
        prefix_map=converter.bimap,
        meta=meta,
    )
