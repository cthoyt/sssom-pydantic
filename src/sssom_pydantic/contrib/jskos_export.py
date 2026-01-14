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
    """Convert mapping(s) to JSKOS using sssom-js.

    :param mappings: a SemanticMapping or a list of SemanticMappings
    :param metadata: metadata about the mapping set
    :param converter: a Converter object

    :returns: a JSKOS concept representing the mapping set, with mappings contained
        within

    .. warning::

        JSKOS does not yet support all SSSOM fields, so a round trip is not possible
    """
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
    """Get mappings from a JSKOS mapping.

    :param concept: a JSKOS concept, which contains ``mappings``
    :param converter: a Converter object used to process the JSKOS object

    :returns: A list of SSSOM mappings

    .. warning::

        JSKOS does not yet support all SSSOM fields, so a round trip is not possible
    """
    return [_process_jskos_mapping(mapping, converter) for mapping in concept.mappings]


def _process_metadata(concept: jskos.Concept) -> MappingSet:
    raise NotImplementedError("metadata processing not yet implemented")


def _process_jskos_mapping(
    jskos_mapping: jskos.Mapping, converter: curies.Converter
) -> SemanticMapping:
    processed_mapping = jskos_mapping.process(converter)

    subject = processed_mapping.from_bundle.member_set[0].reference
    obj = processed_mapping.to_bundle.member_set[0].reference
    justification = processed_mapping.justification
    # TODO why isn't this parsed into a reference upstream?
    predicate = converter.parse_uri(str(processed_mapping.type[0]), strict=True).to_pydantic()

    # `und` means undefined language
    if processed_mapping.note and "und" in processed_mapping.note:
        comment = processed_mapping.note["und"][0]
    else:
        comment = None

    # TODO license doesn't get propagated to JSKOS mapping

    return SemanticMapping(
        subject=subject,
        predicate=predicate,
        object=obj,
        justification=justification,
        comment=comment,
        mapping_date=processed_mapping.created,
    )


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
