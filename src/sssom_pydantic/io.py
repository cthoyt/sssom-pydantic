"""I/O operations for SSSOM."""

from __future__ import annotations

import csv
import logging
from collections import ChainMap, Counter, defaultdict
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, Literal, TextIO, TypeAlias

import curies
import yaml
from curies import Converter, Reference
from tqdm import tqdm

from .api import MappingSet, MappingTool, RequiredSemanticMapping, SemanticMapping
from .constants import DEFAULT_PREFIX_MAP, MULTIVALUED, PREFIX_MAP_KEY, PROPAGATABLE
from .models import Record

__all__ = [
    "Metadata",
    "lint",
    "parse_record",
    "parse_row",
    "read",
    "read_unprocessed",
    "write",
    "write_unprocessed",
]

logger = logging.getLogger(__name__)

#: The type for metadata
Metadata: TypeAlias = dict[str, Any]


def parse_record(record: Record, converter: curies.Converter) -> SemanticMapping:
    """Parse a record into a mapping."""
    subject = converter.parse_curie(record.subject_id, strict=True).to_pydantic(
        name=record.subject_label
    )
    predicate = converter.parse_curie(record.predicate_id, strict=True).to_pydantic(
        name=record.predicate_label
    )
    obj = converter.parse_curie(record.object_id, strict=True).to_pydantic(name=record.object_label)
    mapping_justification = converter.parse_curie(
        record.mapping_justification, strict=True
    ).to_pydantic()

    if record.mapping_tool_id or record.mapping_tool:
        mapping_tool = MappingTool(
            reference=converter.parse_curie(record.mapping_tool_id, strict=True).to_pydantic()
            if record.mapping_tool_id
            else None,
            name=record.mapping_tool,
            version=record.mapping_tool_version,
        )
    elif record.mapping_tool_version:
        raise ValueError("mapping tool version is dependent on having a name or ID")
    else:
        mapping_tool = None

    def _parse_curies(x: list[str] | None) -> list[Reference] | None:
        if not x:
            return None
        return [converter.parse_curie(y, strict=True).to_pydantic() for y in x]

    return SemanticMapping(
        subject=subject,
        predicate=predicate,
        object=obj,
        justification=mapping_justification,
        mapping_tool=mapping_tool,
        mapping_set=MappingSet(
            id=record.mapping_set_id,
            confidence=record.confidence,
            description=record.mapping_set_description,
            source=record.mapping_set_source,
            title=record.mapping_set_title,
            version=record.mapping_set_version,
        ),
        authors=_parse_curies(record.author_id),
        creators=_parse_curies(record.creator_id),
        reviewers=_parse_curies(record.reviewer_id),
        # TODO there's more to do!
    )


def write(
    records: Iterable[RequiredSemanticMapping],
    path: str | Path,
    *,
    metadata: dict[str, Any] | None = None,
    mode: Literal["w", "a"] | None = None,
    converter: curies.Converter | None = None,
) -> None:
    """Write processed records."""
    x = [m.to_record() for m in records]
    write_unprocessed(x, path=path, metadata=metadata, mode=mode, converter=converter)


def write_unprocessed(
    records: Sequence[Record],
    path: str | Path,
    *,
    metadata: dict[str, Any] | None = None,
    mode: Literal["w", "a"] | None = None,
    converter: curies.Converter | None = None,
) -> None:
    """Write unprocessed records."""
    path = Path(path).expanduser().resolve()
    columns = _get_columns(records)

    if metadata is None:
        metadata = {}

    condensation = _get_condensation(records)
    for key, value in condensation.items():
        if key in metadata and metadata[key] != value:
            logger.warning("mismatch between given metadata and observed. overwriting")
        metadata[key] = value

    if converter is None:
        if not metadata.get(PREFIX_MAP_KEY):
            raise ValueError(f"must have {PREFIX_MAP_KEY} in metadata if converter not given")
    else:
        if metadata.get(PREFIX_MAP_KEY):
            raise NotImplementedError
        else:
            metadata[PREFIX_MAP_KEY] = converter.bimap

    # at minimum, this needs to have a CURIE map

    condensed_keys = set(condensation)
    columns = [c for c in columns if c not in condensed_keys]

    with path.open(mode="w" if mode is None else mode) as file:
        for line in yaml.safe_dump(metadata).splitlines():
            print(f"#{line}", file=file)
            # TODO add comment about being written with this software at a given time
        writer = csv.DictWriter(file, columns, delimiter="\t")
        writer.writeheader()
        writer.writerows(
            _unprocess_row(record, condensed_keys=condensed_keys) for record in records
        )


def _get_condensation(records: Iterable[Record]) -> dict[str, Any]:
    values: defaultdict[str, Counter[str | None | tuple[str, ...]]] = defaultdict(Counter)
    for record in records:
        for key in PROPAGATABLE:
            value = getattr(record, key)
            if isinstance(value, list):
                values[key][tuple(sorted(value))] += 1
            elif value is None or isinstance(value, str):
                values[key][value] += 1
            else:
                raise TypeError(f"unhandled value type: {type(value)} for {value}")

    condensed = {}
    for key, counter in values.items():
        if len(counter) != 1:
            continue
        value = next(iter(counter))
        if value is None:
            continue  # no need to unpropagate this
        condensed[key] = value
    return condensed


def _get_columns(records: Iterable[Record]) -> list[str]:
    columns = set()
    for record in records:
        for key in record.model_fields_set:
            if getattr(record, key) is not None:
                columns.add(key)

    # get them in the canonical order
    return [f for f in Record.model_fields if f in columns]


def _unprocess_row(i: Record, condensed_keys: set[str]) -> dict[str, Any]:
    record = i.model_dump(
        exclude_none=True, exclude_unset=True, exclude_defaults=True, exclude=condensed_keys
    )
    for key in MULTIVALUED:
        if (v := record.get(key)) and isinstance(v, str):
            record[key] = "|".join(v)
    return record


def _clean_row(record: dict[str, Any]) -> dict[str, Any]:
    record = {
        key: v_stripped
        for key, value in record.items()
        if key and value and (v_stripped := value.strip()) and v_stripped != "."
    }
    return record


def _preprocess_row(
    record: dict[str, Any], *, metadata: dict[str, Any] | None = None
) -> dict[str, Any]:
    # Step 1: propagate values from the header if it's not explicit in the record
    if metadata:
        for key in PROPAGATABLE.intersection(metadata):
            if not record.get(key):
                value = metadata[key]
                if key in MULTIVALUED and isinstance(value, str):
                    value = [value]
                record[key] = value

    # Step 2: split all lists on the default SSSOM delimiter (pipe)
    for key in MULTIVALUED:
        if (v := record.get(key)) and isinstance(v, str):
            record[key] = [y for x in v.split("|") if (y := x.strip())]

    return record


def parse_row(record: dict[str, str], *, metadata: dict[str, Any] | None = None) -> Record:
    """Parse a row from a SSSOM TSV file, unprocessed."""
    processed_record = _preprocess_row(record, metadata=metadata)
    rv = Record.model_validate(processed_record)
    return rv


def read(
    path: str | Path,
    *,
    metadata_path: str | Path | None = None,
    metadata: Metadata | None = None,
    progress: bool = False,
    converter: curies.Converter | None = None,
) -> tuple[list[SemanticMapping], Converter]:
    """Read and process SSSOM from TSV."""
    unprocessed_records, converter = read_unprocessed(
        path=path,
        metadata_path=metadata_path,
        metadata=metadata,
        progress=progress,
        converter=converter,
    )
    processed_records = [parse_record(record, converter) for record in unprocessed_records]
    return processed_records, converter


def read_unprocessed(
    path: str | Path,
    *,
    metadata_path: str | Path | None = None,
    metadata: Metadata | None = None,
    progress: bool = False,
    converter: curies.Converter | None = None,
) -> tuple[list[Record], Converter]:
    """Read SSSOM TSV into unprocessed records."""
    external_metadata = (
        yaml.safe_load(Path(metadata_path).expanduser().resolve().read_text())
        if metadata_path is not None
        else {}
    )

    if metadata is None:
        metadata = {}

    with Path(path).expanduser().resolve().open() as file:
        columns, inline_metadata = _chomp_frontmatter(file)

        rv_converter = Converter.from_prefix_map(
            ChainMap(
                metadata.pop(PREFIX_MAP_KEY, {}),
                external_metadata.pop(PREFIX_MAP_KEY, {}),
                inline_metadata.pop(PREFIX_MAP_KEY, {}),
                DEFAULT_PREFIX_MAP,
            )
        )

        chained_metadata = dict(ChainMap(metadata, external_metadata, inline_metadata))

        reader = csv.DictReader(file, fieldnames=columns, delimiter="\t")
        reader = tqdm(reader, disable=not progress)
        mappings = [
            parse_row(cleaned_row, metadata=chained_metadata)
            for row in reader
            if (cleaned_row := _clean_row(row))
        ]

    if converter is not None:
        rv_converter = curies.chain([converter, rv_converter])

    return mappings, rv_converter


def _chomp_frontmatter(file: TextIO) -> tuple[list[str], Metadata]:
    # consume from the top of the stream until there's no more preceding #
    header_yaml = ""
    while (line := file.readline()).startswith("#"):
        line = line.lstrip("#").rstrip()
        if not line:
            continue
        header_yaml += line + "\n"

    columns = line.strip().split("\t")

    if not header_yaml:
        rv = {}
    else:
        rv = yaml.safe_load(header_yaml)

    return columns, rv


def lint(path: str | Path) -> None:
    """Lint a file."""
    mappings, converter = read(path)
    mappings = _remove_redundant(mappings)
    write(mappings, path, converter=converter)


def _remove_redundant(mappings: list[SemanticMapping]) -> list[SemanticMapping]:
    return mappings
