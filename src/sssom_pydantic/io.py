"""I/O operations for SSSOM."""

from __future__ import annotations

import csv
import logging
from collections import ChainMap, Counter, defaultdict
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, TextIO, TypeAlias, TypeVar

import curies
import yaml
from curies import Converter, Reference
from pystow.utils import safe_open

from .api import (
    MappingSet,
    MappingTool,
    RequiredSemanticMapping,
    SemanticMapping,
)
from .constants import (
    BUILTIN_CONVERTER,
    MAPPING_SET_SLOTS,
    MULTIVALUED,
    PREFIX_MAP_KEY,
    PROPAGATABLE,
)
from .models import Record
from .process import SemanticMappingHasher, remove_redundant_external, remove_redundant_internal

__all__ = [
    "Metadata",
    "append",
    "append_unprocessed",
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

X = TypeVar("X")
Y = TypeVar("Y")


def _safe_dump_mapping_set(m: Metadata | MappingSet) -> Metadata:
    if isinstance(m, MappingSet):
        return m.model_dump(exclude_none=True, exclude_unset=True)
    return m


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

    def _parse_curie(x: str | None) -> Reference | None:
        if not x:
            return None
        return converter.parse_curie(x, strict=True).to_pydantic()

    return SemanticMapping(
        subject=subject,
        predicate=predicate,
        object=obj,
        justification=mapping_justification,
        predicate_modifier=record.predicate_modifier,
        # core
        record=_parse_curie(record.record_id),
        authors=_parse_curies(record.author_id),
        confidence=record.confidence,
        mapping_tool=mapping_tool,
        license=record.license,
        # remaining
        subject_category=record.subject_category,
        subject_match_field=_parse_curies(record.subject_match_field),
        subject_preprocessing=_parse_curies(record.subject_preprocessing),
        subject_source=_parse_curie(record.subject_source),
        subject_source_version=record.subject_source_version,
        subject_type=record.subject_type,
        predicate_type=_parse_curie(record.predicate_type),
        object_category=record.object_category,
        object_match_field=_parse_curies(record.object_match_field),
        object_preprocessing=_parse_curies(record.object_preprocessing),
        object_source=_parse_curie(record.object_source),
        object_source_version=record.object_source_version,
        object_type=record.subject_type,
        creators=_parse_curies(record.creator_id),
        reviewers=_parse_curies(record.reviewer_id),
        publication_date=record.publication_date,
        mapping_date=record.mapping_date,
        comment=record.comment,
        curation_rule=_parse_curies(record.curation_rule),
        curation_rule_text=record.curation_rule_text,
        # TODO get fancy with rewriting github issues?
        issue_tracker_item=_parse_curie(record.issue_tracker_item),
        mapping_cardinality=record.mapping_cardinality,
        cardinality_scope=record.cardinality_scope,
        mapping_provider=record.mapping_provider,
        mapping_source=_parse_curie(record.mapping_source),
        match_string=record.match_string,
        other=record.other,
        see_also=record.see_also,
        similarity_measure=record.similarity_measure,
        similarity_score=record.similarity_score,
    )


def write(
    mappings: Iterable[RequiredSemanticMapping],
    path: str | Path,
    *,
    metadata: Metadata | None | MappingSet = None,
    converter: curies.Converter | None = None,
) -> None:
    """Write processed records."""
    records, prefixes = _prepare_records(mappings)
    write_unprocessed(records, path=path, metadata=metadata, converter=converter, prefixes=prefixes)


def append(
    mappings: Iterable[RequiredSemanticMapping],
    path: str | Path,
    *,
    metadata: Metadata | MappingSet | None = None,
    converter: curies.Converter | None = None,
) -> None:
    """Append processed records."""
    records, prefixes = _prepare_records(mappings)
    append_unprocessed(
        records, path=path, metadata=metadata, converter=converter, prefixes=prefixes
    )


def _prepare_records(mappings: Iterable[RequiredSemanticMapping]) -> tuple[list[Record], set[str]]:
    records = []
    prefixes: set[str] = set()
    for mapping in mappings:
        prefixes.update(mapping.get_prefixes())
        records.append(mapping.to_record())
    return records, prefixes


def append_unprocessed(
    records: Sequence[Record],
    path: str | Path,
    *,
    metadata: Metadata | MappingSet | None = None,
    converter: curies.Converter | None = None,
    prefixes: set[str] | None = None,
) -> None:
    """Append records to the end of an existing file."""
    path = Path(path).expanduser().resolve()
    with path.open() as file:
        original_columns, _rv = _chomp_frontmatter(file)
    if not original_columns:
        raise ValueError(
            f"can not append {len(records):,} mappings because no headers found in {path}"
        )
    condensed_keys = {"mapping_set_id"}  # this is a hack...
    columns = _get_columns(records)
    new_columns = set(columns).difference(original_columns).difference(condensed_keys)
    if new_columns:
        raise NotImplementedError(
            f"\n\nsssom-pydantic can not yet handle extending columns on append."
            f"\nexisting columns: {original_columns}"
            f"\nnew columns: {new_columns}"
        )
    # TODO compare existing prefixes to new ones
    with path.open(mode="a") as file:
        writer = csv.DictWriter(file, original_columns, delimiter="\t")
        writer.writerows(
            _unprocess_row(record, condensed_keys=condensed_keys) for record in records
        )


def write_unprocessed(
    records: Sequence[Record],
    path: str | Path,
    *,
    metadata: MappingSet | Metadata | None = None,
    converter: curies.Converter | None = None,
    prefixes: set[str] | None = None,
) -> None:
    """Write unprocessed records."""
    path = Path(path).expanduser().resolve()
    columns = _get_columns(records)

    if metadata is None:
        metadata = {}
    else:
        metadata = _safe_dump_mapping_set(metadata)

    condensation = _get_condensation(records)
    for key, value in condensation.items():
        if key in metadata and metadata[key] != value:
            logger.warning("mismatch between given metadata and observed. overwriting")
        metadata[key] = value

    converters = []
    if converter is not None:
        converters.append(converter)
    if prefix_map := metadata.pop(PREFIX_MAP_KEY, {}):
        converters.append(curies.Converter.from_prefix_map(prefix_map))
    if not converters:
        raise ValueError(f"must have {PREFIX_MAP_KEY} in metadata if converter not given")
    converter = curies.chain(converters)

    if prefixes is not None:
        converter = converter.get_subconverter(prefixes)

    # don't add if no prefix map
    if bimap := converter.bimap:
        metadata[PREFIX_MAP_KEY] = bimap

    condensed_keys = set(condensation)
    columns = [column for column in columns if column not in condensed_keys]

    with path.open(mode="w") as file:
        if metadata:
            for line in yaml.safe_dump(metadata).splitlines():
                print(f"#{line}", file=file)
                # TODO add comment about being written with this software at a given time
        writer = csv.DictWriter(file, columns, delimiter="\t")
        writer.writeheader()
        writer.writerows(
            _unprocess_row(record, condensed_keys=condensed_keys) for record in records
        )


def _get_condensation(records: Iterable[Record]) -> dict[str, Any]:
    values: defaultdict[str, Counter[str | float | None | tuple[str, ...]]] = defaultdict(Counter)
    for record in records:
        for key in PROPAGATABLE:
            value = getattr(record, key)
            if isinstance(value, list):
                values[key][tuple(sorted(value))] += 1
            elif value is None or isinstance(value, str | float):
                values[key][value] += 1
            else:
                raise TypeError(f"unhandled value type: {type(value)} for {value}")

    condensed = {}
    for key, counter in values.items():
        if len(counter) != 1:
            continue
        value = next(iter(counter))
        if value is None:
            continue  # no need to un-propagate this
        condensed[key] = value
    return condensed


def _get_columns(records: Iterable[Record]) -> list[str]:
    columns = set()
    for record in records:
        for key in record.model_fields_set:
            if getattr(record, key) is not None:
                columns.add(key)

    # get them in the canonical order, based on how they appear in the
    # record, which mirrors https://w3id.org/sssom/Mapping
    return [column for column in Record.model_fields if column in columns]


def _unprocess_row(record: Record, *, condensed_keys: set[str] | None = None) -> dict[str, Any]:
    rv = record.model_dump(
        exclude_none=True, exclude_unset=True, exclude_defaults=True, exclude=condensed_keys
    )
    for key in MULTIVALUED:
        if (value := rv.get(key)) and isinstance(value, list):
            rv[key] = "|".join(value)
    return rv


def _clean_row(record: dict[str, Any]) -> dict[str, Any]:
    record = {
        key: stripped_value
        for key, value in record.items()
        if key and value and (stripped_value := value.strip()) and stripped_value != "."
    }
    return record


def _preprocess_row(record: dict[str, Any], *, metadata: Metadata | None = None) -> dict[str, Any]:
    # Step 1: propagate values from the header if it's not explicit in the record
    if metadata:
        for key in PROPAGATABLE.intersection(metadata):
            if not record.get(key):
                value = metadata[key]
                # the following conditional fixes common mistakes in
                # encoding a multivalued slot with a single value
                if key in MULTIVALUED and isinstance(value, str):
                    value = [value]
                record[key] = value

    # Step 2: split all lists on the default SSSOM delimiter (pipe)
    for key in MULTIVALUED:
        if (value := record.get(key)) and isinstance(value, str):
            record[key] = [
                stripped_subvalue
                for subvalue in value.split("|")
                if (stripped_subvalue := subvalue.strip())
            ]

    return record


def parse_row(record: dict[str, str], *, metadata: Metadata | None = None) -> Record:
    """Parse a row from a SSSOM TSV file, unprocessed."""
    processed_record = _preprocess_row(record, metadata=metadata)
    rv = Record.model_validate(processed_record)
    return rv


def read(
    path_or_url: str | Path,
    *,
    metadata_path: str | Path | None = None,
    metadata: MappingSet | Metadata | None = None,
    converter: curies.Converter | None = None,
) -> tuple[list[SemanticMapping], Converter, MappingSet]:
    """Read and process SSSOM from TSV."""
    unprocessed_records, rv_converter, mapping_set = read_unprocessed(
        path_or_url=path_or_url,
        metadata_path=metadata_path,
        metadata=metadata,
        converter=converter,
    )
    processed_records = [parse_record(record, rv_converter) for record in unprocessed_records]
    return processed_records, rv_converter, mapping_set


def read_unprocessed(
    path_or_url: str | Path,
    *,
    metadata_path: str | Path | None = None,
    metadata: MappingSet | Metadata | None = None,
    converter: curies.Converter | None = None,
) -> tuple[list[Record], Converter, MappingSet]:
    """Read SSSOM TSV into unprocessed records."""
    if metadata_path is None:
        external_metadata = {}
    else:
        with safe_open(metadata_path, operation="read", representation="text") as file:
            external_metadata = yaml.safe_load(file)

    if metadata is None:
        metadata = {}
    else:
        metadata = _safe_dump_mapping_set(metadata)

    # TODO implement chain operation on MappingSet

    with safe_open(path_or_url, operation="read", representation="text") as file:
        columns, inline_metadata = _chomp_frontmatter(file)

        chained_prefix_map = dict(
            ChainMap(
                metadata.pop(PREFIX_MAP_KEY, {}),
                external_metadata.pop(PREFIX_MAP_KEY, {}),
                inline_metadata.pop(PREFIX_MAP_KEY, {}),
            )
        )

        chained_metadata = dict(ChainMap(metadata, external_metadata, inline_metadata))

        unknown = set(chained_metadata).difference(MAPPING_SET_SLOTS)
        if unknown:
            raise ValueError(f"Found unknown mapping set-level metadata: {sorted(unknown)}")

        reader = csv.DictReader(file, fieldnames=columns, delimiter="\t")
        mappings = [
            parse_row(cleaned_row, metadata=chained_metadata)
            for row in reader
            if (cleaned_row := _clean_row(row))
        ]

    # TODO need to take subset of metadata that wasn't propagated
    mapping_set = MappingSet.model_validate(chained_metadata)

    converters = []
    if converter is not None:
        converters.append(converter)
    if chained_prefix_map:
        converters.append(Converter.from_prefix_map(chained_prefix_map))
    converters.append(BUILTIN_CONVERTER)
    rv_converter = curies.chain(converters)

    return mappings, rv_converter, mapping_set


def _chomp_frontmatter(file: TextIO) -> tuple[list[str], Metadata]:
    # consume from the top of the stream until there's no more preceding #
    header_yaml = ""
    while (line := file.readline()).startswith("#"):
        line = line.lstrip("#").rstrip()
        if not line:
            continue
        header_yaml += line + "\n"

    columns = [
        column_stripped
        for column in line.strip().split("\t")
        if (column_stripped := column.strip())
    ]

    if not header_yaml:
        metadata = {}
    else:
        metadata = yaml.safe_load(header_yaml)

    return columns, metadata


def lint(
    path: str | Path,
    *,
    metadata_path: str | Path | None = None,
    metadata: MappingSet | Metadata | None = None,
    converter: curies.Converter | None = None,
    exclude_mappings: Iterable[SemanticMapping] | None = None,
    exclude_mappings_key: SemanticMappingHasher[X] | None = None,
    drop_duplicates: bool = False,
    drop_duplicates_key: SemanticMappingHasher[Y] | None = None,
) -> None:
    """Lint a file."""
    mappings, converter_processed, mapping_set = read(
        path, metadata_path=metadata_path, metadata=metadata, converter=converter
    )
    if exclude_mappings is not None:
        mappings = remove_redundant_external(mappings, exclude_mappings, key=exclude_mappings_key)
    if drop_duplicates:
        mappings = remove_redundant_internal(mappings, key=drop_duplicates_key)
    mappings = sorted(mappings)
    write(mappings, path, converter=converter_processed, metadata=mapping_set)
