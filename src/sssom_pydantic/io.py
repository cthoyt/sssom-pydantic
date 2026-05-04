"""I/O operations for SSSOM."""

from __future__ import annotations

import contextlib
import csv
import datetime
import logging
import traceback
from collections import ChainMap, Counter, defaultdict
from collections.abc import Collection, Generator, Iterable, Mapping, Sequence
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, NamedTuple, TextIO, TypeAlias, overload

import curies
import yaml
from curies import Converter, Reference
from pydantic import AnyUrl
from pystow.cache import Cached
from pystow.utils import model_dump_yaml, read_pydantic_yaml, safe_open
from tqdm import tqdm
from typing_extensions import TypeVar

from .api import (
    MappingSet,
    MappingSetRecord,
    MappingTool,
    MappingTypeVar,
    SemanticMapping,
    SemanticMappingPredicate,
    _other_to_dict,
    row_to_record,
)
from .constants import (
    BUILTIN_CONVERTER,
    ENTITY_TYPE_LITERAL_TO_REFERENCE,
    MULTIVALUED,
    PREFIX_MAP_KEY,
    PROPAGATABLE,
    EntityTypeLiteral,
    Row,
)
from .models import Record, RecordPredicate
from .process import Hasher, remove_redundant_external, remove_redundant_internal

if TYPE_CHECKING:
    import pandas

__all__ = [
    "CachedSemanticMappings",
    "Metadata",
    "ParseError",
    "SemanticMappingPack",
    "append",
    "append_unprocessed",
    "lint",
    "read",
    "read_iterable",
    "read_unprocessed",
    "record_to_semantic_mapping",
    "row_to_record",
    "row_to_semantic_mapping",
    "to_dataframe",
    "write",
    "write_metadata",
    "write_unprocessed",
]

logger = logging.getLogger(__name__)

#: The type for metadata
Metadata: TypeAlias = dict[str, Any]

X = TypeVar("X")
Y = TypeVar("Y")
Stage: TypeAlias = Literal["raw", "processing"]


class ParseError(NamedTuple):
    """An error during SSSOM parsing and processing that causes a row to be unrecoverable."""

    line_number: int
    exception: Exception
    stage: Stage

    def format_exception(self) -> str:
        """Format the exception as a string."""
        return _get_exc(self.exception)


def _get_exc(exc: Exception) -> str:
    file = StringIO()
    traceback.print_exception(exc, file=file)
    file.seek(0)
    return file.read()


def _safe_dump_mapping_set(m: Metadata | MappingSet | MappingSetRecord) -> Metadata:
    match m:
        case MappingSet():
            return m.to_record().model_dump(exclude_none=True, exclude_unset=True, mode="json")
        case MappingSetRecord():
            return m.model_dump(exclude_none=True, exclude_unset=True, mode="json")
        case _:
            return m


def row_to_semantic_mapping(
    row: Mapping[str, str | list[str]],
    converter: curies.Converter,
    *,
    propagatable: dict[str, str | list[str]] | None = None,
) -> SemanticMapping:
    """Get a semantic mapping from a row.

    :param row: The row from a SSSOM TSV file
    :param converter: A converter for parsing CURIEs
    :param propagatable: Extra data coming from SSSOM TSV frontmatter to get propagated
        into each record

    :returns: A semantic mapping
    """
    cleaned_row = _clean_row(row)
    record = row_to_record(cleaned_row, propagatable=propagatable)
    return record_to_semantic_mapping(record, converter)


def record_to_semantic_mapping(
    record: Record, converter: curies.Converter, *, line_number: int | None = None
) -> SemanticMapping:
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
            reference=converter.parse(record.mapping_tool_id, strict=True).to_pydantic()
            if record.mapping_tool_id
            else None,
            name=record.mapping_tool,
            version=record.mapping_tool_version,
        )
    elif record.mapping_tool_version:
        raise ValueError("mapping tool version is dependent on having a name or ID")
    else:
        mapping_tool = None

    def _parse_curies_or_uris(curies_or_uris: list[str] | None) -> list[Reference] | None:
        if not curies_or_uris:
            return None
        return [
            converter.parse(curie_or_uri, strict=True).to_pydantic()
            for curie_or_uri in curies_or_uris
        ]

    def _parse_curie_or_uri(curie_or_uri: str | None) -> Reference | None:
        if not curie_or_uri:
            return None
        return converter.parse(curie_or_uri, strict=True).to_pydantic()

    def _safe_entity_type(entity_type: EntityTypeLiteral | None) -> Reference | None:
        if entity_type is None:
            return None
        return ENTITY_TYPE_LITERAL_TO_REFERENCE[entity_type]

    return SemanticMapping(
        subject=subject,
        predicate=predicate,
        object=obj,
        justification=mapping_justification,
        predicate_modifier=record.predicate_modifier,
        # core
        record=_parse_curie_or_uri(record.record_id),
        authors=_parse_curies_or_uris(record.author_id),
        confidence=record.confidence,
        reviewer_agreement=record.reviewer_agreement,
        mapping_tool=mapping_tool,
        license=record.license,
        # remaining
        subject_category=_parse_curie_or_uri(record.subject_category),
        subject_match_field=_parse_curies_or_uris(record.subject_match_field),
        subject_preprocessing=_parse_curies_or_uris(record.subject_preprocessing),
        subject_source=_parse_curie_or_uri(record.subject_source),
        subject_source_version=record.subject_source_version,
        subject_type=_safe_entity_type(record.subject_type),
        predicate_type=_safe_entity_type(record.predicate_type),
        object_category=_parse_curie_or_uri(record.object_category),
        object_match_field=_parse_curies_or_uris(record.object_match_field),
        object_preprocessing=_parse_curies_or_uris(record.object_preprocessing),
        object_source=_parse_curie_or_uri(record.object_source),
        object_source_version=record.object_source_version,
        object_type=_safe_entity_type(record.object_type),
        creators=_parse_curies_or_uris(record.creator_id),
        reviewers=_parse_curies_or_uris(record.reviewer_id),
        publication_date=record.publication_date,
        review_date=record.review_date,
        mapping_date=record.mapping_date,
        comment=record.comment,
        curation_rule=_parse_curies_or_uris(record.curation_rule),
        curation_rule_text=record.curation_rule_text,
        # TODO get fancy with rewriting github issues?
        issue_tracker_item=_parse_curie_or_uri(record.issue_tracker_item),
        cardinality=record.mapping_cardinality,
        cardinality_scope=record.cardinality_scope,
        provider=record.mapping_provider,
        source=_parse_curie_or_uri(record.mapping_source),
        match_string=record.match_string,
        other=_other_to_dict(record.other, line_number=line_number) if record.other else None,
        see_also=record.see_also,
        similarity_measure=record.similarity_measure,
        similarity_score=record.similarity_score,
    )


def write(
    mappings: Iterable[MappingTypeVar],
    path: str | Path | TextIO,
    *,
    metadata: MappingSet | Metadata | MappingSetRecord | None = None,
    converter: curies.Converter | None = None,
    exclude_mappings: Iterable[MappingTypeVar] | None = None,
    exclude_mappings_key: Hasher[MappingTypeVar, X] | None = None,
    drop_duplicates: bool = False,
    drop_duplicates_key: Hasher[MappingTypeVar, Y] | None = None,
    sort: bool = False,
    columns: Sequence[str] | None = None,
    exclude_columns: Collection[str] | None = None,
    exclude_prefixes: Collection[str] | None = None,
    condense: bool = True,
    subset_converter: bool = True,
) -> None:
    """Write processed records."""
    if exclude_mappings is not None:
        mappings = remove_redundant_external(mappings, exclude_mappings, key=exclude_mappings_key)
    if drop_duplicates:
        mappings = remove_redundant_internal(mappings, key=drop_duplicates_key)
    if sort:
        mappings = sorted(mappings)

    if subset_converter:
        records, prefixes = _prepare_records(mappings)
    else:
        records = [m.to_record() for m in mappings]
        prefixes = set()

    if metadata is not None:
        if converter is None:
            raise NotImplementedError("when passing non-parsed metadata, need a converter")
        metadata = _get_mapping_set(metadata, converter)
        prefixes.update(metadata.get_prefixes())
    if exclude_prefixes:
        prefixes.difference_update(exclude_prefixes)
    write_unprocessed(
        records,
        path=path,
        metadata=metadata,
        converter=converter,
        prefixes=prefixes if subset_converter else None,
        columns=columns,
        exclude_columns=exclude_columns,
        condense=condense,
    )


def _get_mapping_set(
    m: MappingSet | Metadata | MappingSetRecord, converter: Converter
) -> MappingSet:
    if isinstance(m, MappingSet):
        return m
    if isinstance(m, MappingSetRecord):
        return m.process(converter)
    raise NotImplementedError(f"not sure what to do with {type(m)}")


def append(
    mappings: Iterable[SemanticMapping],
    path: str | Path,
    *,
    metadata: Metadata | MappingSet | None = None,
    converter: curies.Converter | None = None,
    exclude_columns: Collection[str] | None = None,
) -> None:
    """Append processed records."""
    records, prefixes = _prepare_records(mappings)
    append_unprocessed(
        records,
        path=path,
        metadata=metadata,
        converter=converter,
        prefixes=prefixes,
        exclude_columns=exclude_columns,
    )


def _prepare_records(mappings: Iterable[SemanticMapping]) -> tuple[list[Record], set[str]]:
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
    exclude_columns: Collection[str] | None = None,
) -> None:
    """Append records to the end of an existing file."""
    path = Path(path).expanduser().resolve()
    with path.open() as file:
        original_columns, _rv, _frontmatter_length = _chomp_frontmatter(file)
    if not original_columns:
        raise ValueError(
            f"can not append {len(records):,} mappings because no headers found in {path}"
        )
    exclude = {"mapping_set_id"}.union(exclude_columns or [])  # this is a hack...
    columns = _get_columns(records)
    new_columns = set(columns).difference(original_columns).difference(exclude)
    if new_columns:
        raise NotImplementedError(
            f"\n\nsssom-pydantic can not yet handle extending columns on append."
            f"\nexisting columns: {original_columns}"
            f"\nnew columns: {new_columns}"
        )
    # TODO compare existing prefixes to new ones
    with path.open(mode="a") as file:
        writer = csv.DictWriter(file, original_columns, delimiter="\t")
        writer.writerows(_unprocess_row(record, exclude=exclude) for record in records)


def write_unprocessed(
    records: Sequence[Record],
    path: str | Path | TextIO,
    *,
    metadata: MappingSet | Metadata | MappingSetRecord | None = None,
    converter: curies.Converter | None = None,
    prefixes: set[str] | None = None,
    columns: Sequence[str] | None = None,
    exclude_columns: Collection[str] | None = None,
    condense: bool = True,
) -> None:
    """Write unprocessed records.

    :param records: records to write
    :param path: the path to a file or a file-like object to write to
    :param metadata: metadata to use
    :param converter: converter to use
    :param prefixes: if given, subsets the converter
    :param columns: explicitly set what columns should be output.
        Results in taking more than one pass over the mappings
    :param exclude_columns: explicitly set what columns should not be output
    :param condense: condense mappings into mapping set metadata.
        Results in taking more than one pass over the mappings
    """
    metadata = _get_metadata(metadata)

    if condense:
        condensation = _get_condensation(records)
        for key, value in condensation.items():
            if key in metadata and metadata[key] != value:
                logger.warning("mismatch between given metadata and observed. overwriting")
            metadata[key] = value
    else:
        condensation = {}

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

    if columns is None:
        columns = _get_columns(records)
        exclude = set(condensation).union(exclude_columns or [])
        columns = [column for column in columns if column not in exclude]
    else:
        exclude = None

    with safe_open(path, operation="write", representation="text") as file:
        write_metadata(metadata, file)
        writer = csv.DictWriter(file, columns, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(_unprocess_row(record, exclude=exclude) for record in records)


def write_metadata(metadata: MappingSetRecord | Metadata | MappingSet | None, file: TextIO) -> None:
    """Write SSSOM metadata for the top of a TSV."""
    mapping_set_record = _get_mapping_set_record(metadata)
    if mapping_set_record is None:
        return
    # TODO add comment about being written with this software at a given time
    yaml_str = model_dump_yaml(mapping_set_record, exclude_none=True, exclude_unset=True)
    for line in yaml_str.splitlines():
        file.write(f"#{line}\n")


CondensationTypes: TypeAlias = str | float | None | datetime.date | tuple[str, ...]


def _get_condensation(records: Iterable[Record]) -> dict[str, CondensationTypes]:
    values: defaultdict[str, Counter[CondensationTypes]] = defaultdict(Counter)
    for record in records:
        for key in PROPAGATABLE:
            value = getattr(record, key)
            if isinstance(value, list):
                values[key][tuple(sorted(value))] += 1
            elif isinstance(value, AnyUrl):
                values[key][str(value)] += 1
            elif value is None or isinstance(value, str | float | datetime.date):
                values[key][value] += 1
            else:
                raise TypeError(f"unhandled value type: {type(value)} for {value}")

    condensed: dict[str, CondensationTypes] = {}
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


def _unprocess_row(record: Record, *, exclude: set[str] | None = None) -> dict[str, Any]:
    rv = record.model_dump(
        exclude_none=True, exclude_unset=True, exclude_defaults=True, exclude=exclude
    )
    for key in MULTIVALUED:
        if (value := rv.get(key)) and isinstance(value, list):
            rv[key] = "|".join(value)
    return rv


def _clean_row(row: Mapping[str, str | list[str]]) -> Row:
    """Clean a raw row from a SSSOM TSV file."""
    rv = {}
    for key, value in row.items():
        if not key or not value:
            continue
        if isinstance(value, str):
            value = value.strip()
        elif isinstance(value, list):
            value = [vs for v in value if (vs := v.strip())]
        else:
            raise TypeError(f"unhandled value type: {type(value)} for {value}")
        if not value:
            continue
        rv[key] = value
    return rv


class SemanticMappingPack(NamedTuple):
    """The results of reading and processing a SSSOM TSV file."""

    mappings: list[SemanticMapping]
    converter: Converter
    mapping_set: MappingSet


ExtendedReadType: TypeAlias = tuple[list[SemanticMapping], Converter, MappingSet, list[ParseError]]


# docstr-coverage:excused `overload`
@overload
def read(
    path_or_url: str | Path | TextIO,
    *,
    metadata_path: str | Path | None,
    metadata: MappingSet | MappingSetRecord | Metadata | None,
    converter: curies.Converter | None,
    progress: bool,
    progress_kwargs: dict[str, Any] | None,
    record_predicate: RecordPredicate | None,
    semantic_mapping_predicate: SemanticMappingPredicate | None,
    return_errors: Literal[True] = True,
) -> ExtendedReadType: ...


# docstr-coverage:excused `overload`
@overload
def read(
    path_or_url: str | Path | TextIO,
    *,
    metadata_path: str | Path | None = ...,
    metadata: MappingSet | MappingSetRecord | Metadata | None = ...,
    converter: curies.Converter | None = ...,
    progress: bool = ...,
    progress_kwargs: dict[str, Any] | None = ...,
    record_predicate: RecordPredicate | None = ...,
    semantic_mapping_predicate: SemanticMappingPredicate | None = ...,
    return_errors: Literal[False] = False,
) -> SemanticMappingPack: ...


# docstr-coverage:excused `overload`
@overload
def read(
    path_or_url: str | Path | TextIO,
    *,
    metadata_path: str | Path | None = ...,
    metadata: MappingSet | MappingSetRecord | Metadata | None = ...,
    converter: curies.Converter | None = ...,
    progress: bool = ...,
    progress_kwargs: dict[str, Any] | None = ...,
    record_predicate: RecordPredicate | None = ...,
    semantic_mapping_predicate: SemanticMappingPredicate | None = ...,
    return_errors: Literal[True] = True,
) -> ExtendedReadType: ...


# docstr-coverage:excused `overload`
@overload
def read(
    path_or_url: str | Path | TextIO,
    *,
    metadata_path: str | Path | None = ...,
    metadata: MappingSet | MappingSetRecord | Metadata | None = ...,
    converter: curies.Converter | None = ...,
    progress: bool = ...,
    progress_kwargs: dict[str, Any] | None = ...,
    record_predicate: RecordPredicate | None = ...,
    semantic_mapping_predicate: SemanticMappingPredicate | None = ...,
    return_errors: None = ...,
) -> SemanticMappingPack: ...


def read(
    path_or_url: str | Path | TextIO,
    *,
    metadata_path: str | Path | None = None,
    metadata: MappingSet | MappingSetRecord | Metadata | None = None,
    converter: curies.Converter | None = None,
    progress: bool = False,
    progress_kwargs: dict[str, Any] | None = None,
    record_predicate: RecordPredicate | None = None,
    semantic_mapping_predicate: SemanticMappingPredicate | None = None,
    return_errors: bool | None = None,
) -> SemanticMappingPack | ExtendedReadType:
    """Read and process SSSOM from TSV."""
    with read_iterable(
        path_or_url=path_or_url,
        metadata_path=metadata_path,
        metadata=metadata,
        converter=converter,
        progress=progress,
        progress_kwargs=progress_kwargs,
        record_predicate=record_predicate,
        semantic_mapping_predicate=semantic_mapping_predicate,
    ) as t:
        mappings: list[SemanticMapping] = []
        errors: list[ParseError] = []
        for x in t.mappings:
            if isinstance(x, SemanticMapping):
                mappings.append(x)
            elif return_errors:
                errors.append(x)
        if return_errors:
            return mappings, t.converter, t.mapping_set, errors
        else:
            return SemanticMappingPack(mappings, t.converter, t.mapping_set)


class ReadTuple(NamedTuple):
    """A tuple returned from streaming reading of a SSSOM file."""

    mappings: Iterable[SemanticMapping | ParseError]
    converter: Converter
    mapping_set: MappingSet


@contextlib.contextmanager
def read_iterable(
    path_or_url: str | Path | TextIO,
    *,
    metadata_path: str | Path | None = None,
    metadata: MappingSet | MappingSetRecord | Metadata | None = None,
    converter: curies.Converter | None = None,
    progress: bool = False,
    progress_kwargs: dict[str, Any] | None = None,
    record_predicate: RecordPredicate | None = None,
    semantic_mapping_predicate: SemanticMappingPredicate | None = None,
) -> Generator[ReadTuple, None, None]:
    """Read and process SSSOM from TSV in an iterable way."""
    with read_unprocessed_iterable(
        path_or_url=path_or_url,
        metadata_path=metadata_path,
        metadata=metadata,
        converter=converter,
        progress=progress,
        progress_kwargs=progress_kwargs,
        record_predicate=record_predicate,
    ) as t:

        def _process() -> Iterable[SemanticMapping | ParseError]:
            for line_number, record in t.records:
                if isinstance(record, ParseError):
                    yield record
                    continue
                try:
                    mapping = record_to_semantic_mapping(
                        record, t.converter, line_number=line_number
                    )
                except ValueError as e:
                    logger.debug("[line %d] failed to process record: %s", line_number, record)
                    yield ParseError(line_number, e, stage="processing")
                else:
                    if semantic_mapping_predicate is not None and not semantic_mapping_predicate(
                        mapping
                    ):
                        continue
                    yield mapping

        mappings = _process()
        yield ReadTuple(mappings, t.converter, t.mapping_set)


# FIXME delete
def _get_metadata(metadata: MappingSet | MappingSetRecord | Metadata | None) -> Metadata:
    mapping_set_record = _get_mapping_set_record(metadata)
    if mapping_set_record is None:
        return {}
    return mapping_set_record.model_dump(exclude_none=True, exclude_unset=True, mode="json")


def _get_mapping_set_record(
    metadata: MappingSet | MappingSetRecord | Metadata | None,
) -> MappingSetRecord | None:
    if isinstance(metadata, dict):
        return MappingSetRecord.model_validate(metadata)
    elif isinstance(metadata, MappingSet):
        return metadata.to_record()
    elif metadata is None:
        return None
    elif isinstance(metadata, MappingSetRecord):
        return metadata
    else:
        raise TypeError


class RecordTuple(NamedTuple):
    """Return the unprocessed record."""

    line_number: int
    record: Record | ParseError


class ReadUnprocessedTuple(NamedTuple):
    """The results returned from reading a SSSOM file without processing."""

    records: list[Record]
    converter: Converter
    mapping_set: MappingSet


class ReadUnprocessedStreamTuple(NamedTuple):
    """The results returned from reading a SSSOM file without processing with streaming."""

    records: Iterable[RecordTuple]
    converter: Converter
    mapping_set: MappingSet


def read_unprocessed(
    path_or_url: str | Path | TextIO,
    *,
    metadata_path: str | Path | None = None,
    metadata: MappingSet | MappingSetRecord | Metadata | None = None,
    converter: curies.Converter | None = None,
    progress: bool = False,
    progress_kwargs: dict[str, Any] | None = None,
    record_predicate: RecordPredicate | None = None,
    return_errors: bool = False,
) -> ReadUnprocessedTuple:
    """Read SSSOM TSV into unprocessed records."""
    with read_unprocessed_iterable(
        path_or_url=path_or_url,
        metadata_path=metadata_path,
        metadata=metadata,
        converter=converter,
        progress=progress,
        progress_kwargs=progress_kwargs,
        record_predicate=record_predicate,
    ) as t:
        records: list[Record] = []
        errors: list[ParseError] = []
        for _, record in t.records:
            if isinstance(record, Record):
                records.append(record)
            elif return_errors:
                errors.append(record)
        if return_errors:
            raise NotImplementedError
        return ReadUnprocessedTuple(
            records,
            t.converter,
            t.mapping_set,
        )


@contextlib.contextmanager
def read_unprocessed_iterable(
    path_or_url: str | Path | TextIO,
    *,
    metadata_path: str | Path | None = None,
    metadata: MappingSet | MappingSetRecord | Metadata | None = None,
    converter: curies.Converter | None = None,
    progress: bool = False,
    progress_kwargs: dict[str, Any] | None = None,
    record_predicate: RecordPredicate | None = None,
) -> Generator[ReadUnprocessedStreamTuple, None, None]:
    """Read SSSOM TSV into unprocessed records."""
    if metadata_path is None:
        second_metadata = None
    else:
        second_metadata = read_pydantic_yaml(metadata_path, MappingSetRecord)

    first_metadata = _get_mapping_set_record(metadata)

    _tqdm_kwargs = {
        "disable": not progress,
        "desc": "Reading SSSOM records",
        "unit_scale": True,
    }
    if progress_kwargs:
        _tqdm_kwargs.update(progress_kwargs)

    with safe_open(path_or_url, representation="text", operation="read") as file:
        columns, inline_metadata, frontmatter_length = _chomp_frontmatter(file)
        mapping_set_record = _chain_mapping_set_record(
            first_metadata, second_metadata, inline_metadata
        )
        _row_to_record = mapping_set_record.get_parser()
        reader = csv.DictReader(file, fieldnames=columns, delimiter="\t")
        reader = tqdm(reader, **_tqdm_kwargs)

        def _iterate_record_tuples() -> Iterable[RecordTuple]:
            for line_number, row in enumerate(reader, start=frontmatter_length + 1):
                cleaned_row = _clean_row(row)
                if not cleaned_row:
                    continue
                try:
                    record = _row_to_record(cleaned_row)
                except ValueError as e:
                    logger.debug("[line %d] failed to parse row: %s", line_number, cleaned_row)
                    yield RecordTuple(line_number, ParseError(line_number, e, stage="raw"))
                else:
                    if record_predicate is not None and not record_predicate(record):
                        continue
                    yield RecordTuple(line_number, record)

        records = _iterate_record_tuples()
        converter = _chain_converters(converter, mapping_set_record)
        mapping_set = mapping_set_record.process(converter)
        yield ReadUnprocessedStreamTuple(records, converter, mapping_set)


def _chain_converters(
    converter: Converter | None, mapping_set_record: MappingSetRecord
) -> Converter:
    converters = []
    if converter is not None:
        converters.append(converter)
    if mapping_set_record.curie_map:
        converters.append(Converter.from_prefix_map(mapping_set_record.curie_map))
    converters.append(BUILTIN_CONVERTER)
    rv = curies.chain(converters)
    return rv


def _chain_mapping_set_record(*mapping_set_records: MappingSetRecord | None) -> MappingSetRecord:
    chained_prefix_map = _cm(
        mapping_set_record.curie_map
        for mapping_set_record in mapping_set_records
        if mapping_set_record is not None and mapping_set_record.curie_map
    )
    # todo more detailed chain for other list members?
    #  creator_id, creator_label, see_also, mapping_set_source, extension_definitions

    chained_metadata = _cm(
        mapping_set_record.model_dump(exclude_none=True, exclude_unset=True, exclude={"curie_map"})
        for mapping_set_record in mapping_set_records
        if mapping_set_record is not None
    )
    chained_metadata["curie_map"] = chained_prefix_map
    mapping_set = MappingSetRecord.model_validate(chained_metadata)
    return mapping_set


def _cm(m: Iterable[dict[str, Any]]) -> dict[str, Any]:
    return dict(ChainMap(*m))


def _chomp_frontmatter(file: TextIO) -> tuple[list[str], MappingSetRecord | None, int]:
    # consume from the top of the stream until there's no more preceding #
    count = 0
    header_yaml = ""
    while (line := file.readline()).startswith("#"):
        count += 1
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
        rv = None
    else:
        rv = MappingSetRecord.model_validate(yaml.safe_load(header_yaml))

    return columns, rv, count


def lint(
    path: str | Path,
    *,
    metadata_path: str | Path | None = None,
    metadata: MappingSet | Metadata | None = None,
    converter: curies.Converter | None = None,
    exclude_mappings: Iterable[SemanticMapping] | None = None,
    exclude_mappings_key: Hasher[SemanticMapping, X] | None = None,
    drop_duplicates: bool = False,
    drop_duplicates_key: Hasher[SemanticMapping, Y] | None = None,
) -> None:
    """Lint a file."""
    mappings, converter_processed, mapping_set = read(
        path, metadata_path=metadata_path, metadata=metadata, converter=converter
    )
    write(
        mappings,
        path,
        converter=converter_processed,
        metadata=mapping_set,
        exclude_mappings=exclude_mappings,
        exclude_mappings_key=exclude_mappings_key,
        drop_duplicates=drop_duplicates,
        drop_duplicates_key=drop_duplicates_key,
        sort=True,
    )


class CachedSemanticMappings(Cached[SemanticMappingPack]):
    """Make a function lazily cache SSSOM."""

    def load(self) -> SemanticMappingPack:
        """Load data from the cache as a dataframe."""
        return read(self.path)

    def dump(self, read_type: SemanticMappingPack) -> None:
        """Dump data to the cache as a dataframe."""
        write(
            read_type.mappings,
            self.path,
            converter=read_type.converter,
            metadata=read_type.mapping_set,
        )


def to_dataframe(mappings: Iterable[SemanticMapping]) -> pandas.DataFrame:
    """Construct a pandas dataframe that represents the SSSOM TSV format.

    :param mappings: An iterable of SSSOM mappings.

    :returns: A pandas dataframe that represents the SSSOM TSV format.

    .. seealso::

        If you want compatibility with :mod:`sssom`, then use
        :func:`sssom_pydantic.contrib.sssompy.mappings_to_msdf`
    """
    import pandas

    rv = pandas.DataFrame(_unprocess_row(mapping.to_record()) for mapping in mappings)
    return rv
