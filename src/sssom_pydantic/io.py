"""I/O operations for SSSOM."""

from __future__ import annotations

import csv
from collections import ChainMap
from pathlib import Path
from typing import Any, Literal, TextIO, TypeAlias

import curies
import yaml
from curies import Converter, Reference
from tqdm import tqdm

from .api import MappingSet, MappingTool, SemanticMapping
from .constants import DEFAULT_PREFIX_MAP, MULTIVALUED, PREFIX_MAP_KEY, PROPAGATABLE
from .models import Record

__all__ = [
    "Metadata",
    "parse_record",
    "parse_row",
    "read",
    "read_unprocessed",
    "write",
    "write_unprocessed",
]

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
    )


def write(
    records: list[SemanticMapping],
    path: str | Path,
    *,
    metadata: dict[str, Any] | None = None,
    mode: Literal["w", "a"] | None = None,
) -> None:
    """Write processed records."""
    x = [m.to_record() for m in records]
    write_unprocessed(x, path=path, metadata=metadata, mode=mode)


def write_unprocessed(
    records: list[Record],
    path: str | Path,
    *,
    metadata: dict[str, Any] | None = None,
    mode: Literal["w", "a"] | None = None,
) -> None:
    """Write unprocessed records."""
    path = Path(path).expanduser().resolve()
    columns = _get_columns(records)

    # TODO condense operation

    with path.open(mode="w" if mode is None else mode) as file:
        if metadata:
            for line in yaml.safe_dump(metadata).splitlines():
                print(f"#{line}", file=file)
        writer = csv.DictWriter(file, columns, delimiter="\t")
        writer.writeheader()
        writer.writerows(_unprocess_row(record) for record in records)


def _get_columns(records: list[Record]) -> list[str]:
    columns = set()
    for record in records:
        for key in record.model_fields_set:
            if getattr(record, key) is not None:
                columns.add(key)

    # get them in the canonical order
    return [f for f in Record.model_fields if f in columns]


def _unprocess_row(i: Record) -> dict[str, Any]:
    record = i.model_dump(exclude_none=True, exclude_unset=True, exclude_defaults=True)
    for key in MULTIVALUED:
        if (v := record.get(key)) and isinstance(v, str):
            record[key] = "|".join(v)
    return record


def _preprocess_row(record: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    record = {k: v.strip() for k, v in record.items() if v and v.strip() and v.strip() != "."}

    # Step 1: propagate values from the header if it's not explicit in the record
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


def parse_row(record: dict[str, str], metadata: dict[str, Any]) -> Record:
    """Parse a row from a SSSOM TSV file, unprocessed."""
    return Record.model_validate(_preprocess_row(record, metadata))


def read(
    path: str | Path,
    *,
    metadata_path: str | Path | None = None,
    metadata: Metadata | None = None,
    progress: bool = False,
    converter: curies.Converter | None = None,
) -> tuple[list[SemanticMapping], Converter]:
    """Read and process SSSOM from TSV."""
    records, converter = read_unprocessed(
        path=path,
        metadata_path=metadata_path,
        metadata=metadata,
        progress=progress,
        converter=converter,
    )
    rr = [parse_record(record, converter) for record in records]
    return rr, converter


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
        rv = [parse_row(record, chained_metadata) for record in reader]

    if converter is not None:
        rv_converter = curies.chain([converter, rv_converter])

    return rv, rv_converter


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
