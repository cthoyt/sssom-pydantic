"""Convert semantic mappings into JSKOS format."""

import subprocess
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import curies
import jskos

import sssom_pydantic
from sssom_pydantic.io import ReadType

if TYPE_CHECKING:
    import jskos

    from sssom_pydantic import MappingSet, MappingSetRecord, Metadata, SemanticMapping

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


def from_jskos(concept: jskos.Concept) -> ReadType:
    """Get mappings from a JSKOS mapping."""
    with tempfile.TemporaryDirectory() as temporary_directory:
        path = Path(temporary_directory).joinpath("tmp.sssom.json")
        path.write_text(
            concept.model_dump_json(
                indent=2, exclude_none=True, exclude_defaults=True, exclude_unset=True
            )
        )
        return from_jskos_path(path)


def from_jskos_path(path: Path) -> ReadType:
    """Convert SSSOM TSV to JSKOS using sssom-js."""
    with _convert(path, "jskos", "tsv") as processed_path:
        return sssom_pydantic.read(processed_path)


def _path_to_jskos(sssom_tsv_path: Path) -> jskos.Concept:
    """Convert SSSOM TSV to JSKOS using sssom-js."""
    import jskos

    with _convert(sssom_tsv_path, "tsv", "jskos") as path:
        text = path.read_text()
    return jskos.Concept.model_validate_json(text)


@contextmanager
def _convert(
    input_path: Path, input_format: str, output_format: str
) -> Generator[Path, None, None]:
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
        # these are concepts, not sure if the KOS class actually
        # makes any sense
        text = output_path.read_text()
        if not text:
            raise ValueError(
                f"sssom-js produced no output.\n\nstderr: {result.stderr.decode('utf-8')}"
            )
        yield output_path
