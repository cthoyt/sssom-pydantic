"""I/O for the :mod:`sssom` package."""

from __future__ import annotations

from typing import TYPE_CHECKING

import curies

from ..api import MappingSet, MappingSetRecord, SemanticMapping
from ..io import Metadata, _safe_dump_mapping_set, _unprocess_row

if TYPE_CHECKING:
    import pandas
    import sssom

__all__ = [
    "mappings_to_msdf",
]

SSSOM_PY_DEFAULT_LICENSE = "https://w3id.org/sssom/license/unspecified"


def _mappings_to_df(mappings: list[SemanticMapping]) -> pandas.DataFrame:
    """Construct a pandas dataframe that represents the SSSOM TSV format."""
    import pandas

    rows = [_unprocess_row(mapping.to_record()) for mapping in mappings]
    rv = pandas.DataFrame(rows)
    return rv


def mappings_to_msdf(
    mappings: list[SemanticMapping],
    converter: curies.Converter,
    metadata: MappingSet | Metadata | MappingSetRecord,
    *,
    linkml_validate: bool = False,
) -> sssom.MappingSetDataFrame:
    """Construct a SSSOM-py mapping set dataframe object."""
    from sssom import MappingSetDataFrame
    from sssom.parsers import from_sssom_dataframe

    df = _mappings_to_df(mappings)
    meta = _safe_dump_mapping_set(metadata)

    # SSSOM-Py insists that license is a required field,
    # but also automatically adds the following stub in
    # case you didn't put one
    meta.setdefault("license", SSSOM_PY_DEFAULT_LICENSE)

    if not linkml_validate:
        # we can trust that SSSOM-Pydantic makes a correct
        # dataframe, so we normally don't have to go through
        # the weird round-trip implemented in from_sssom_dataframe
        # through LinkML object I/O
        return MappingSetDataFrame(df=df, converter=converter, metadata=meta)

    return from_sssom_dataframe(df, prefix_map=converter, meta=meta)
