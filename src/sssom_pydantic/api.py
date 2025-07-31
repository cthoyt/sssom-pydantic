"""This is a placeholder for putting the main code for your module."""

from __future__ import annotations

import csv
import datetime
from collections import ChainMap
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Literal, TypeAlias

import yaml
from curies import Reference
from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "PREDICATE_TYPES",
    "Cardinality",
    "Record",
    "read",
]

Cardinality: TypeAlias = Literal["1:1", "1:n", "n:1", "1:0", "0:1", "n:n"]

#: Allowed predicate types
PREDICATE_TYPES = [
    Reference(prefix="owl", identifier="Class"),
    Reference(prefix="owl", identifier="ObjectProperty"),
    Reference(prefix="owl", identifier="DataProperty"),
    Reference(prefix="owl", identifier="AnnotationProperty"),
    Reference(prefix="owl", identifier="NamedIndividual"),
    Reference(prefix="skos", identifier="Concept"),
    Reference(prefix="rdfs", identifier="Resource"),
    Reference(prefix="rdfs", identifier="Literal"),
    Reference(prefix="rdfs", identifier="Datatype"),
    Reference(prefix="rdf", identifier="Property"),
    Reference(prefix="sssom", identifier="ComposedEntityExpression"),
]

PROPAGATABLE: set[str] = {"mappping_set_id"}


class Record(BaseModel):
    """Represents an SSSOM record (i.e., a row in a SSSOM TSV file).

    A SSSOM record contains both the mapping set information and mapping information.
    """

    model_config = ConfigDict(frozen=True)

    record_id: str | None = Field(None)

    mapping_set_confidence: float | None = Field(None)
    mapping_set_description: str | None = Field(None)
    mapping_set_id: str = Field(...)
    mapping_set_source: str | None = Field(None)
    mapping_set_title: str | None = Field(None)
    mapping_set_version: str | None = Field(None)

    subject_id: str = Field(...)
    subject_label: str | None = Field(None)
    subject_category: str | None = Field(None)
    subject_match_field: str | None = Field(None)
    subject_preprocessing: str | None = Field(None)
    subject_source: str | None = Field(None)
    subject_source_version: str | None = Field(None)
    subject_type: str | None = Field(None)

    predicate_id: str = Field(...)
    predicate_label: str | None = Field(None)
    predicate_modifier: Literal["Not"] | None = Field(None)
    predicate_type: Reference | None = Field(
        None,
        examples=PREDICATE_TYPES,
        description="See https://mapping-commons.github.io/sssom/predicate_type/. "
        "Values allowed are from https://mapping-commons.github.io/sssom/EntityTypeEnum/",
    )

    object_id: str = Field(...)
    object_label: str | None = Field(None)
    object_category: str | None = Field(None)
    object_match_field: str | None = Field(None)
    object_preprocessing: str | None = Field(None)
    object_source: str | None = Field(None)
    object_source_version: str | None = Field(None)
    object_type: str | None = Field(
        None,
        description="See https://mapping-commons.github.io/sssom/object_type/. "
        "Values allowed are from https://mapping-commons.github.io/sssom/EntityTypeEnum/",
    )

    mapping_justification: str = Field(...)

    author_id: str | None = Field(None)
    author_label: str | None = Field(None)
    creator_id: str | None = Field(None)
    creator_label: str | None = Field(None)
    reviewer_id: str | None = Field(None)
    reviewer_label: str | None = Field(None)

    publication_date: datetime.date | None = Field(None)
    mapping_date: datetime.date | None = Field(None)

    comment: str | None = Field(None)
    confidence: float | None = Field(None)
    curation_rule: str | None = Field(None)
    curation_rule_text: str | None = Field(None)
    issue_tracker_item: str | None = Field(None)
    license: str | None = Field(None)
    #: see https://mapping-commons.github.io/sssom/MappingCardinalityEnum/
    mapping_cardinality: Cardinality | None = Field(None)
    mapping_provider: str | None = Field(None)
    mapping_source: str | None = Field(None)
    mapping_tool: str | None = Field(None)
    mapping_tool_id: str | None = Field(None)
    mapping_tool_version: str | None = Field(None)
    match_string: str | None = Field(None)
    other: str | None = Field(None)
    see_also: str | None = Field(None)
    similarity_measure: str | None = Field(None)
    similarity_score: float | None = Field(None)


def read(
    path: str | Path, metadata_path: str | Path, metadata: dict[str, Any] | None
) -> Iterable[Record]:
    """Read a raw file."""
    rv = []
    with Path(path).expanduser().resolve().open() as file:
        # consume from the top of the stream until there's no more preceding #
        header_yaml = ""
        while (line := file.readline()).startswith("#"):
            line = line.lstrip("#").rstrip()
            if not line:
                continue
            header_yaml += line + "\n"

        inline_metadata = yaml.safe_load(header_yaml) if header_yaml else {}
        external_metadata = (
            yaml.safe_load(metadata_path.read_text()) if metadata_path is not None else {}
        )
        if metadata is None:
            metadata = {}

        chained_metadata = dict(ChainMap(metadata, external_metadata, inline_metadata))

        for record in csv.DictReader(file, delimiter="\t"):
            for key in PROPAGATABLE.intersection(chained_metadata):
                if not record.get(key):
                    record[key] = chained_metadata[key]
            model = Record.model_validate(record)
            rv.append(model)
    return rv
