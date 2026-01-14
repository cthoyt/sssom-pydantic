"""Convert semantic mappings into JSKOS format."""

import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import curies
import jskos

import sssom_pydantic

if TYPE_CHECKING:
    import jskos

    from sssom_pydantic import MappingSet, MappingSetRecord, Metadata, SemanticMapping

__all__ = [
    "to_jskos",
]


def to_jskos(
    mappings: SemanticMapping | list[SemanticMapping],
    *,
    metadata: MappingSet | Metadata | MappingSetRecord | None = None,
    converter: curies.Converter | None = None,
) -> jskos.Concept:
    """Convert mapping(s) to JSKOS using sssom-js."""
    if isinstance(mappings, SemanticMapping):
        mappings = [mappings]
    with tempfile.TemporaryDirectory() as temporary_directory:
        path = Path(temporary_directory).joinpath("tmp.sssom.tsv")
        sssom_pydantic.write(
            mappings,
            path,
            metadata=metadata,
            converter=converter,
        )
        return _path_to_jskos(path)


def _path_to_jskos(path: Path) -> jskos.Concept:
    """Convert SSSOM TSV to JSKOS using sssom-js."""
    import jskos

    with tempfile.TemporaryDirectory() as temporary_directory:
        # Convert the SSSOM TSV to JSKOS using the sssom-js package
        # on NPM (https://www.npmjs.com/package/sssom-js)
        jskos_path = Path(temporary_directory).joinpath("tmp.sssom.json")
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
