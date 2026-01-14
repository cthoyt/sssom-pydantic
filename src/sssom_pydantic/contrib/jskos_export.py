"""Convert semantic mappings into JSKOS format."""

import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import curies
import jskos

import sssom_pydantic
from sssom_pydantic import SemanticMapping

if TYPE_CHECKING:
    import jskos

    from sssom_pydantic import MappingSet, MappingSetRecord, Metadata

__all__ = [
    "from_jskos",
    "from_jskos_path",
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


def from_jskos(concept: jskos.Concept, converter: curies.Converter) -> list[SemanticMapping]:
    """Get mappings from a JSKOS mapping."""
    return []


def from_jskos_path(path: Path, converter: curies.Converter) -> list[SemanticMapping]:
    """Convert SSSOM TSV to JSKOS using sssom-js."""
    from jskos import Concept

    concept = Concept.model_validate_json(path.read_text())
    return from_jskos(concept, converter)


def _path_to_jskos(sssom_tsv_path: Path) -> jskos.Concept:
    """Convert SSSOM TSV to JSKOS using sssom-js."""
    import jskos

    text = _convert(sssom_tsv_path, "tsv", "jskos")
    return jskos.Concept.model_validate_json(text)


def _convert(input_path: Path, input_format: str, output_format: str) -> str:
    with tempfile.TemporaryDirectory() as temporary_directory:
        # Convert the SSSOM TSV to JSKOS using the sssom-js package
        # on NPM (https://www.npmjs.com/package/sssom-js)
        output_path = Path(temporary_directory).joinpath("tmp.sssom.json")
        result = subprocess.run(  # noqa:S603
            [  # noqa:S607
                "npx",
                "sssom-js",
                "--from",
                input_format,
                "--to",
                output_format,
                "--output",
                output_path.as_posix(),
                input_path.as_posix(),
            ],
            stderr=subprocess.PIPE,
        )
        if not output_path.is_file():
            raise ValueError(
                f"sssom-js produced no output.\n\nstderr: {result.stderr.decode('utf-8')}"
            )
        text = output_path.read_text()
        if not text:
            raise ValueError(
                f"sssom-js produced no output.\n\nstderr: {result.stderr.decode('utf-8')}"
            )
        return text
