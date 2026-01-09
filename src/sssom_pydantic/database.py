"""Database model.

.. code-block:: python

    from sssom_pydantic.database import SemanticMappingDatabase
    from sssom_pydantic.api import mapping_hash_v1

    database = SemanticMappingDatabase.memory(semantic_mapping_hash=mapping_hash_v1)
    database.read("https://w3id.org/biopragmatics/biomappings/biomappings.sssom.tsv")

"""

from __future__ import annotations

import contextlib
import datetime
from collections.abc import Callable, Collection, Generator, Iterable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Concatenate, Literal, ParamSpec, cast, overload

import curies
import sqlmodel
from curies import NamableReference, Reference
from curies.database import (
    get_reference_list_sa_column,
    get_reference_sa_column,
)
from curies.vocabulary import manual_mapping_curation
from pydantic import AnyUrl
from sqlalchemy import Dialect, TypeDecorator
from sqlalchemy.engine.base import Engine
from sqlalchemy.sql.type_api import TypeEngine
from sqlmodel import JSON, Column, Field, Session, SQLModel, String, and_, col, func, or_, select
from sqlmodel.sql._expression_select_cls import SelectOfScalar
from typing_extensions import Self

import sssom_pydantic
from sssom_pydantic import MappingTool, Metadata, SemanticMapping
from sssom_pydantic.api import MappingSet, MappingSetRecord, SemanticMappingHash
from sssom_pydantic.models import Cardinality
from sssom_pydantic.process import UNSURE, Mark, curate, publish
from sssom_pydantic.query import Query

if TYPE_CHECKING:
    from sqlalchemy.sql.selectable import ColumnExpressionArgument  # type:ignore[attr-defined]

__all__ = [
    "DEFAULT_SORT",
    "NEGATIVE_MAPPING_CLAUSE",
    "POSITIVE_MAPPING_CLAUSE",
    "UNCURATED_NOT_UNSURE_CLAUSE",
    "UNCURATED_UNSURE_CLAUSE",
    "SemanticMappingDatabase",
    "SemanticMappingModel",
    "clauses_from_query",
]

P = ParamSpec("P")


class MappingToolTypeDecorator(TypeDecorator[MappingTool]):
    """A SQLAlchemy type decorator for a mapping tool."""

    impl: ClassVar[type[TypeEngine[str]]] = JSON  # type:ignore[misc]
    #: Set SQLAlchemy caching to true
    cache_ok: ClassVar[bool] = True  # type:ignore[misc]

    def process_bind_param(
        self, value: MappingTool | None, dialect: Dialect
    ) -> dict[str, Any] | None:
        """Convert the Python object into a database value."""
        if value is None:
            return None
        return value.model_dump()

    def process_result_value(
        self, value: dict[str, Any] | None, dialect: Dialect
    ) -> MappingTool | None:
        """Convert the database value into a Python object."""
        if value is None:
            return None
        return MappingTool.model_validate(value)


class AnyURLTypeDecorator(TypeDecorator[AnyUrl]):
    """A SQLAlchemy type decorator for a URL."""

    impl: ClassVar[type[TypeEngine[str]]] = String  # type:ignore[misc]
    #: Set SQLAlchemy caching to true
    cache_ok: ClassVar[bool] = True  # type:ignore[misc]

    def process_bind_param(self, value: AnyUrl | None, dialect: Dialect) -> str | None:
        """Convert the Python object into a database value."""
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value: str | None, dialect: Dialect) -> AnyUrl | None:
        """Convert the database value into a Python object."""
        if value is None:
            return None
        return AnyUrl(value)


class SemanticMappingModel(SQLModel, table=True):
    """A model."""

    id: int | None = Field(default=None, primary_key=True)

    # required
    subject: Reference = Field(sa_column=get_reference_sa_column())
    subject_name: str | None = Field(None)
    predicate: Reference = Field(sa_column=get_reference_sa_column())
    object: Reference = Field(sa_column=get_reference_sa_column())
    object_name: str | None = Field(None)
    justification: Reference = Field(..., sa_column=get_reference_sa_column())
    predicate_modifier: Literal["Not"] | None = Field(None, sa_type=String)

    # core
    record: Reference | None = Field(None, sa_column=get_reference_sa_column())
    authors: list[Reference] | None = Field(None, sa_column=get_reference_list_sa_column())
    confidence: float | None = Field(None)
    mapping_tool: MappingTool | None = Field(None, sa_column=Column(MappingToolTypeDecorator()))
    license: str | None = Field(None)

    # rest
    subject_category: str | None = Field(None)
    subject_match_field: list[Reference] | None = Field(
        None, sa_column=get_reference_list_sa_column()
    )
    subject_preprocessing: list[Reference] | None = Field(
        None, sa_column=get_reference_list_sa_column()
    )
    subject_source: Reference | None = Field(None, sa_column=get_reference_sa_column())
    subject_source_version: str | None = Field(None)
    subject_type: Reference | None = Field(None, sa_column=get_reference_sa_column())

    predicate_type: Reference | None = Field(None, sa_column=get_reference_sa_column())

    object_category: str | None = Field(None)
    object_match_field: list[Reference] | None = Field(
        None, sa_column=get_reference_list_sa_column()
    )
    object_preprocessing: list[Reference] | None = Field(
        None, sa_column=get_reference_list_sa_column()
    )
    object_source: Reference | None = Field(None, sa_column=get_reference_sa_column())
    object_source_version: str | None = Field(None)
    object_type: Reference | None = Field(None, sa_column=get_reference_sa_column())

    creators: list[Reference] | None = Field(None, sa_column=get_reference_list_sa_column())
    reviewers: list[Reference] | None = Field(None, sa_column=get_reference_list_sa_column())

    publication_date: datetime.date | None = Field(None)
    mapping_date: datetime.date | None = Field(None)

    comment: str | None = Field(None)
    curation_rule: list[Reference] | None = Field(None, sa_column=get_reference_list_sa_column())
    curation_rule_text: list[str] | None = Field(None, sa_type=JSON)
    issue_tracker_item: Reference | None = Field(None, sa_column=get_reference_sa_column())

    #: see https://mapping-commons.github.io/sssom/MappingCardinalityEnum/
    #: and https://w3id.org/sssom/mapping_cardinality
    cardinality: Cardinality | None = Field(None, sa_type=String)
    cardinality_scope: list[str] | None = Field(None, sa_type=JSON)
    # https://w3id.org/sssom/mapping_provider
    provider: AnyUrl | None = Field(None, sa_column=Column(AnyURLTypeDecorator()))
    # https://w3id.org/sssom/mapping_source
    source: Reference | None = Field(None, sa_column=get_reference_sa_column())

    match_string: list[str] | None = Field(None, sa_type=JSON)

    other: dict[str, str] | None = Field(None, sa_type=JSON)
    see_also: list[str] | None = Field(None, sa_type=JSON)
    similarity_measure: str | None = Field(None)
    similarity_score: float | None = Field(None)

    @classmethod
    def from_semantic_mapping(cls, mapping: SemanticMapping) -> Self:
        """Get from a non-ORM mapping."""
        d = mapping.model_dump()
        # do this explicitly since the model might not be smart enough
        # to fully dump a NamableReference, since it's only annotated
        # as a regular Reference
        if subject_name := mapping.subject_name:
            d["subject_name"] = subject_name
        if object_name := mapping.object_name:
            d["object_name"] = object_name
        return cls.model_validate(d)

    def to_semantic_mapping(self) -> SemanticMapping:
        """Get a non-ORM mapping."""
        d = self.model_dump()
        if subject_name := d.pop("subject_name", None):
            d["subject"]["name"] = subject_name
            d["subject"] = NamableReference.model_validate(d["subject"])
        if object_name := d.pop("object_name", None):
            d["object"]["name"] = object_name
            d["object"] = NamableReference.model_validate(d["object"])
        return SemanticMapping.model_validate(d)


class SemanticMappingDatabase:
    """Interact with a database."""

    def __init__(
        self,
        *,
        engine: Engine,
        semantic_mapping_hash: SemanticMappingHash,
        session_cls: type[Session] | None = None,
    ) -> None:
        """Construct a database.

        :param engine: SQLAlchemy engine instance
        :param semantic_mapping_hash: A function that deterministically hashes a mapping.
            This is required until the SSSOM specification
            `defines a standard hashing procedure <https://github.com/mapping-commons/sssom/issues/436>`_.
        :param session_cls: SQLAlchemy session class. By default, this uses :class:`sqlmodel.Session
        """
        self.engine = engine
        self.session_cls = session_cls if session_cls is not None else Session
        self._hsh = semantic_mapping_hash
        SQLModel.metadata.create_all(self.engine)

    @classmethod
    def from_connection(
        cls,
        *,
        connection: str,
        semantic_mapping_hash: SemanticMappingHash,
        session_cls: type[Session] | None = None,
    ) -> Self:
        """Construct a database by a connection string."""
        return cls(
            engine=sqlmodel.create_engine(connection),
            semantic_mapping_hash=semantic_mapping_hash,
            session_cls=session_cls,
        )

    @classmethod
    def memory(
        cls,
        *,
        semantic_mapping_hash: SemanticMappingHash,
        session_cls: type[Session] | None = None,
    ) -> Self:
        """Construct an in-memory database."""
        return cls.from_connection(
            connection="sqlite:///:memory:",
            semantic_mapping_hash=semantic_mapping_hash,
            session_cls=session_cls,
        )

    @contextlib.contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Open a context manager for a session."""
        with self.session_cls(self.engine) as session:
            yield session

    def count_mappings(
        self, where_clauses: Query | list[ColumnExpressionArgument[bool]] | None = None
    ) -> int:
        """Count the mappings in the database."""
        with self.get_session() as session:
            statement = select(func.count()).select_from(SemanticMappingModel)
            if where_clauses is None:
                pass
            elif isinstance(where_clauses, Query):
                statement = statement.where(*clauses_from_query(where_clauses))
            else:
                statement = statement.where(*where_clauses)
            return session.exec(statement).one()

    def add_mapping(self, mapping: SemanticMapping) -> Reference:
        """Add a mapping to the database."""
        rv = self.add_mappings([mapping])
        return rv[0]

    def add_mappings(self, mappings: Iterable[SemanticMapping]) -> list[Reference]:
        """Add mappings to the database."""
        rv: list[Reference] = []
        with self.get_session() as session:
            for mapping in mappings:
                reference = self._hsh(mapping)
                session.add(
                    SemanticMappingModel.from_semantic_mapping(
                        mapping.model_copy(update={"record": reference})
                    )
                )
                rv.append(reference)
            session.commit()
        return rv

    @staticmethod
    def _get_mapping_by_reference(reference: Reference) -> SelectOfScalar[SemanticMappingModel]:
        return select(SemanticMappingModel).where(SemanticMappingModel.record == reference)

    def delete_mapping(self, reference: Reference | SemanticMapping) -> None:
        """Delete a mapping from the database."""
        reference = self._ensure(reference)
        with self.get_session() as session:
            if obj := session.exec(self._get_mapping_by_reference(reference)).first():
                session.delete(obj)
                session.commit()

    def _ensure(self, reference: Reference | SemanticMapping) -> Reference:
        if isinstance(reference, SemanticMapping):
            return self._hsh(reference)
        return reference

    # docstr-coverage:excused `overload`
    @overload
    def get_mapping(
        self, reference: Reference, *, strict: Literal[True] = ...
    ) -> SemanticMappingModel: ...

    # docstr-coverage:excused `overload`
    @overload
    def get_mapping(
        self, reference: Reference, *, strict: Literal[False] = ...
    ) -> SemanticMappingModel | None: ...

    def get_mapping(
        self, reference: Reference, *, strict: bool = False
    ) -> SemanticMappingModel | None:
        """Get a mapping."""
        with self.get_session() as session:
            s = session.exec(self._get_mapping_by_reference(reference))
            if strict:
                return s.one()
            else:
                return s.first()

    def get_mappings(
        self,
        where_clauses: Query | list[ColumnExpressionArgument[bool]] | None = None,
        limit: int | None = None,
        offset: int | None = None,
        order_by: ColumnExpressionArgument[Any] | list[ColumnExpressionArgument[Any]] | None = None,
    ) -> Sequence[SemanticMappingModel]:
        """Get mappings."""
        with self.get_session() as session:
            statement = select(SemanticMappingModel)

            if where_clauses is None:
                pass
            elif isinstance(where_clauses, Query):
                statement = statement.where(*clauses_from_query(where_clauses))
            else:
                statement = statement.where(*where_clauses)

            if limit is not None:
                statement = statement.limit(limit)
            if offset is not None:
                statement = statement.offset(offset)

            if order_by is None:
                pass
            elif isinstance(order_by, list):
                statement = statement.order_by(*order_by)
            else:
                statement = statement.order_by(order_by)

            return session.exec(statement).all()

    def read(
        self,
        path: str | Path,
        metadata: MappingSet | MappingSetRecord | Metadata | None = None,
        converter: curies.Converter | None = None,
        **kwargs: Any,
    ) -> list[Reference]:
        """Read mappings from a file into the database."""
        mappings, _converter, _metadata = sssom_pydantic.read(
            path, metadata=metadata, converter=converter, **kwargs
        )
        return self.add_mappings(mappings)

    def write(
        self,
        path: str | Path,
        *,
        metadata: MappingSet | Metadata | MappingSetRecord | None = None,
        converter: curies.Converter | None = None,
        exclude_columns: Collection[str] | None = None,
        where_clauses: Query | list[ColumnExpressionArgument[bool]] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> None:
        """Write the database to a file."""
        mappings = self.get_mappings(where_clauses=where_clauses, limit=limit, offset=offset)
        mapping_it = (m.to_semantic_mapping() for m in mappings)
        sssom_pydantic.write(
            mapping_it,
            path,
            metadata=metadata,
            converter=converter,
            exclude_columns=exclude_columns,
        )

    def curate(
        self,
        reference: Reference,
        authors: Reference | list[Reference],
        mark: Mark,
        confidence: float | None = None,
        add_date: bool = True,
        **kwargs: Any,
    ) -> Reference:
        """Curate a mapping and return the new mapping's record."""
        if isinstance(authors, Reference):
            authors = [authors]
        return self._mutate(
            reference,
            curate,
            authors=authors,
            mark=mark,
            confidence=confidence,
            add_date=add_date,
            **kwargs,
        )

    def publish(
        self,
        reference: Reference,
        date: datetime.date | None = None,
    ) -> Reference:
        """Publish a mapping and return the new mapping's record."""
        return self._mutate(reference, publish, date=date)

    def _mutate(
        self,
        reference: Reference,
        f: Callable[Concatenate[SemanticMapping, P], SemanticMapping],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> Reference:
        mapping = self.get_mapping(reference)
        if mapping is None:
            raise KeyError
        new_mapping = f(mapping.to_semantic_mapping(), *args, **kwargs)
        new_mapping = new_mapping.model_copy(update={"record": self._hsh(new_mapping)})
        self.add_mapping(new_mapping)
        self.delete_mapping(reference)
        return cast(Reference, new_mapping.record)


POSITIVE_MAPPING_CLAUSE = and_(
    SemanticMappingModel.justification == manual_mapping_curation,
    SemanticMappingModel.predicate_modifier.is_(None),  # type:ignore[union-attr]
)
NEGATIVE_MAPPING_CLAUSE = and_(
    SemanticMappingModel.justification == manual_mapping_curation,
    SemanticMappingModel.predicate_modifier == "Not",
)
UNCURATED_NOT_UNSURE_CLAUSE = and_(
    SemanticMappingModel.justification != manual_mapping_curation,
    or_(
        col(SemanticMappingModel.comment).is_(None),
        ~col(SemanticMappingModel.comment).contains(UNSURE),
    ),
)
UNCURATED_UNSURE_CLAUSE = and_(
    SemanticMappingModel.justification != manual_mapping_curation,
    col(SemanticMappingModel.comment).is_not(None),
    col(SemanticMappingModel.comment).contains(UNSURE),
)

#: The default sort order by subject, predicate, and object CURIEs
#: that can be passed to :meth:`SemanticMappingDatabase.get_mappings`
#: ``order_by`` argument
DEFAULT_SORT = [
    SemanticMappingModel.subject,
    SemanticMappingModel.predicate,
    SemanticMappingModel.object,
]

#: A mapping from :class:`Query` fields to functions that produce appropriate
#: clauses for database querying
QUERY_TO_CLAUSE: dict[str, Callable[[str], ColumnExpressionArgument[bool] | None]] = {
    "query": lambda value: or_(
        col(SemanticMappingModel.subject).icontains(value.lower()),
        col(SemanticMappingModel.subject_name).icontains(value.lower()),
        col(SemanticMappingModel.object).icontains(value.lower()),
        col(SemanticMappingModel.object_name).icontains(value.lower()),
        func.json_extract(SemanticMappingModel.mapping_tool, "$.name").icontains(value.lower()),
    ),
    "subject_prefix": lambda value: col(SemanticMappingModel.subject).icontains(value.lower()),
    "subject_query": lambda value: or_(
        col(SemanticMappingModel.subject).icontains(value.lower()),
        col(SemanticMappingModel.subject_name).icontains(value.lower()),
    ),
    "object_query": lambda value: or_(
        col(SemanticMappingModel.object).icontains(value.lower()),
        col(SemanticMappingModel.object_name).icontains(value.lower()),
    ),
    "object_prefix": lambda value: col(SemanticMappingModel.object).icontains(value.lower()),
    "prefix": lambda value: or_(
        col(SemanticMappingModel.subject).icontains(value.lower()),
        col(SemanticMappingModel.object).icontains(value.lower()),
    ),
    "mapping_tool": lambda value: or_(
        func.json_extract(SemanticMappingModel.mapping_tool, "$.name").icontains(value.lower()),
    ),
    "same_text": lambda value: and_(
        SemanticMappingModel.predicate == "skos:exactMatch",
        (
            _str_norm(SemanticMappingModel.subject_name)
            == _str_norm(SemanticMappingModel.object_name)
        )
        if value
        else or_(
            col(SemanticMappingModel.subject_name).is_(None),
            col(SemanticMappingModel.object_name).is_(None),
            and_(
                col(SemanticMappingModel.subject_name).is_not(None),
                col(SemanticMappingModel.object_name).is_not(None),
                _str_norm(SemanticMappingModel.subject_name)
                != _str_norm(SemanticMappingModel.object_name),
            ),
        ),
    )
    if value is not None
    else None,
}


def _str_norm(column: Any) -> Any:
    return func.lower(func.replace(column, "-", ""))


def clauses_from_query(query: Query | None = None) -> list[ColumnExpressionArgument[bool]]:
    """Get clauses from the query."""
    if query is None:
        return []
    return [
        clause
        for name in Query.model_fields
        if (value := getattr(query, name)) is not None
        and (clause := QUERY_TO_CLAUSE[name](value)) is not None
    ]
