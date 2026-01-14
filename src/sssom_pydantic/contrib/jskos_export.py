"""Convert semantic mappings into JSKOS format."""

import subprocess
import tempfile
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

import curies
import jskos
from jskos import Concept

import sssom_pydantic

if TYPE_CHECKING:
    import jskos

    from sssom_pydantic import MappingSet, MappingSetRecord, Metadata, SemanticMapping

__all__ = [
    "mapping_set_to_jskos",
    "mapping_to_jskos",
    "mapping_to_jskos_oracle",
    "path_to_jskos_oracle",
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


def mapping_to_jskos_oracle(
    mapping: SemanticMapping,
    metadata: MappingSet | Metadata | MappingSetRecord | None,
    converter: curies.Converter,
) -> jskos.Concept:
    """Convert a mapping to JSKOS using sssom-js."""
    with tempfile.TemporaryDirectory() as td:
        path = Path(td).joinpath("example.sssom.tsv")
        sssom_pydantic.write(
            [mapping],
            path,
            metadata=metadata,
            converter=converter,
        )
        return path_to_jskos_oracle(path)


def path_to_jskos_oracle(path: Path) -> jskos.Concept:
    """Convert SSSOM TSV to JSKOS using sssom-js."""
    import jskos

    with tempfile.TemporaryDirectory() as td:
        # Convert the SSSOM TSV to JSKOS using the sssom-js package
        # on NPM (https://www.npmjs.com/package/sssom-js)
        jskos_path = Path(td).joinpath("example.sssom.json")
        result = subprocess.run(  # noqa:S603
            [  # noqa:S607
                "npx",
                "sssom-js",
                "--from",
                "tsv",
                "--to",
                "jskos",
                "--output",
                jskos_path.as_posix(),
                path.as_posix(),
            ],
            stderr=subprocess.PIPE,
        )
        # these are concepts, not sure if the KOS class actually
        # makes any sense
        text = jskos_path.read_text()
        if not text:
            raise ValueError(
                f"sssom-js produced no output.\n\nstderr: {result.stderr.decode('utf-8')}"
            )

        return jskos.Concept.model_validate_json(text)
