"""A Neo4j implementation of a semantic mapping repository."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Sequence
from contextlib import closing
from typing import TYPE_CHECKING, Any, Concatenate, Literal, ParamSpec, TypeVar, cast, overload

import curies
from curies import NamableReference, Reference
from tqdm import tqdm
from typing_extensions import LiteralString

from .repo import CURIENotFoundError, SemanticMappingRepository
from ..api import SemanticMapping, SemanticMappingHash
from ..query import Query

if TYPE_CHECKING:
    import neo4j

__all__ = ["Neo4jSemanticMappingRepository"]

P = ParamSpec("P")
R = TypeVar("R")


class Neo4jSemanticMappingRepository(SemanticMappingRepository):
    """Neo4j implementation of a semantic mapping repository."""

    driver: neo4j.Driver

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        *,
        semantic_mapping_hash: SemanticMappingHash | None = None,
        converter: curies.Converter,
    ) -> None:
        """Initialize the client.

        :param uri: The URI of the Neo4j database.
        :param user: The username for the Neo4j database.
        :param password: The password for the Neo4j database.
        """
        import neo4j

        super().__init__(semantic_mapping_hash=semantic_mapping_hash, converter=converter)

        auth: tuple[str, str] | None
        if user is not None and password is not None:
            auth = user, password
        else:
            auth = None
        self.driver = neo4j.GraphDatabase.driver(uri=uri, auth=auth, max_connection_lifetime=180)

    def __del__(self) -> None:
        self.driver.close()

    def drop_all(self) -> None:
        """Drop all nodes and edges."""
        cypher = "MATCH (n) DETACH DELETE n;"
        self._write(cypher)

    def _write(self, cypher: LiteralString, *args: Any, **kwargs: Any) -> None:
        with closing(self.driver.session()) as session:
            session.execute_write(_get_worker(cypher), *args, **kwargs)

    def add_mappings(
        self, mappings: Iterable[SemanticMapping], *, progress: bool = False
    ) -> list[Reference]:
        """Add mappings to the database."""
        cypher: LiteralString = """
            UNWIND $batch AS row
            MERGE (subject:Entity {curie: row.subject})
              SET subject.name = row.subject_label
            MERGE (object:Entity {curie: row.object})
              SET object.name = row.object_label
            WITH subject, object, row
            MERGE (m:SemanticMapping {id: row.id})
              SET m.triple_id = row.triple_id
              SET m.predicate = row.predicate
              SET m.subject = row.subject
              SET m.subject_label = row.subject_label
              SET m.object = row.object
              SET m.object_label = row.object_label
              SET m.justification = row.justification
              SET m.rest = row.rest
            MERGE (subject)-[:subject_of]->(m)
            MERGE (object)-[:object_of]->(m)
        """
        batch = []
        references = []
        exclude_fields = {
            "record",
            "subject",
            "predicate",
            "object",
            "justification",
            "subject_label",
        }
        for mapping in tqdm(
            mappings, disable=not progress, leave=False, desc="Preparing mappings for Neo4j"
        ):
            reference = self.hash_mapping(mapping)
            references.append(reference)
            batch.append(
                {
                    "id": reference.identifier,
                    "triple_id": self.converter.hash_triple(mapping),
                    "subject": mapping.subject.curie,
                    "subject_label": mapping.subject_name,
                    "predicate": mapping.predicate.curie,
                    "object": mapping.object.curie,
                    "object_label": mapping.object_name,
                    "justification": mapping.justification.curie,
                    "rest": mapping.model_dump_json(
                        exclude=exclude_fields,
                        exclude_none=True,
                        exclude_unset=True,
                        exclude_defaults=True,
                    ),
                }
            )
        self._write(cypher, batch=batch)
        return references

    def count_mappings(self, where_clauses: Query | None = None) -> int:
        """Count the mappings in the database."""
        cypher, params = self._construct(where_clauses, count=True)

        def _count_nodes(tx: neo4j.ManagedTransaction, **kwargs: Any) -> int:
            result = tx.run(cypher, **kwargs)
            return cast(int, result.single()["total"])

        with closing(self.driver.session()) as session:
            return cast(int, session.execute_read(_count_nodes, **params))

    def count_entities(self, where_clauses: Query | None = None) -> int:
        """Count the entities in the database."""
        if where_clauses is not None:
            raise NotImplementedError("need to implement filtering on entity counts for neo4j")

        def _count_nodes(tx: neo4j.ManagedTransaction) -> int:
            result = tx.run("MATCH (n:Entity) RETURN count(n) AS total")
            return cast(int, result.single()["total"])

        with closing(self.driver.session()) as session:
            return cast(int, session.execute_read(_count_nodes))

    def delete_mapping(self, reference: Reference | SemanticMapping) -> None:
        """Delete a mapping from the database."""

        def _delete_node(tx: neo4j.ManagedTransaction, identifier: str) -> int:
            result = tx.run(
                """
                MATCH (p:SemanticMapping {id: $id})
                DETACH DELETE p
                RETURN count(p) AS deleted
                """,
                id=identifier,
            )
            # 1 if found and deleted, 0 if not found
            return result.single()["deleted"]  # type:ignore

        with self.driver.session() as session:
            session.execute_write(_delete_node, self._ensure(reference).identifier)

    # docstr-coverage:excused `overload`
    @overload
    def get_mapping(
        self, reference: Reference, *, strict: Literal[True] = ...
    ) -> SemanticMapping: ...

    # docstr-coverage:excused `overload`
    @overload
    def get_mapping(
        self, reference: Reference, *, strict: Literal[False] = ...
    ) -> SemanticMapping | None: ...

    def get_mapping(self, reference: Reference, *, strict: bool = False) -> SemanticMapping | None:
        """Get a mapping."""

        def _get_node(tx: neo4j.ManagedTransaction, uid: str) -> dict[str, Any] | None:
            result = tx.run("MATCH (p:SemanticMapping {id: $uid}) RETURN p", uid=uid)
            record = result.single()
            return record["p"] if record else None

        with self.driver.session() as session:
            node = session.execute_read(_get_node, reference.identifier)
        if node is not None:
            return self._from_data(node)
        elif strict:
            raise CURIENotFoundError(reference)
        else:
            return None

    def get_mappings(
        self,
        where_clauses: Query | None = None,
        limit: int | None = None,
        offset: int | None = None,
        order_by: str | None = None,
    ) -> Sequence[SemanticMapping]:
        """Get mappings."""
        cypher, params = self._construct(
            where_clauses, limit=limit, offset=offset, order_by=order_by, count=False
        )

        def _get_nodes(tx: neo4j.ManagedTransaction, **kwargs: Any) -> list[dict[str, Any]]:
            result = tx.run(cypher, **kwargs)
            return [record["p"] for record in result]

        with self.driver.session(database="neo4j") as session:
            nodes = session.execute_read(_get_nodes, **params)
            return [self._from_data(node) for node in nodes]

    @staticmethod
    def _construct(
        where_clauses: Query | None = None,
        *,
        limit: int | None = None,
        offset: int | None = None,
        order_by: str | None = None,
        count: bool,
    ) -> tuple[str, dict[str, str | int]]:
        params: dict[str, str | int] = {}
        cypher = "MATCH (p:SemanticMapping)"
        if where_clauses is not None and (where_val := _clauses_from_query(where_clauses)):
            cypher += where_val[0]
            params.update(where_val[1])

        if count:
            cypher += " RETURN count(p) AS total"
            return cypher, params

        cypher += " RETURN p"
        if order_by is not None and (order_val := _get_order_by(order_by)):
            cypher += order_val
        if offset is not None:
            cypher += " SKIP $offset"
            params["offset"] = offset
        if limit is not None:
            cypher += " LIMIT $limit"
            params["limit"] = limit
        return cypher, params

    @staticmethod
    def _from_data(node: neo4j.Node) -> SemanticMapping:
        data = dict(node)
        data.update(json.loads(data.pop("rest")))
        rv = SemanticMapping.model_validate(data)
        model_update = {}
        if subject_label := data.get("subject_label"):
            model_update["subject"] = NamableReference(
                prefix=rv.subject.prefix, identifier=rv.subject.identifier, name=subject_label
            )
        if object_label := data.get("object_label"):
            model_update["object"] = NamableReference(
                prefix=rv.object.prefix, identifier=rv.object.identifier, name=object_label
            )
        if model_update:
            rv = rv.model_copy(update=model_update)
        return rv


def _get_order_by(key: str | None) -> str | None:
    match key:
        case None:
            return None
        case "confidence":
            return " ORDER BY p.confidence"
        case "date":
            return " ORDER BY p.mapping_date"
        case "date-published":
            return " ORDER BY p.published_date"
        case "date-reviewed":
            return " ORDER BY p.review_date"
        case "subject":
            return " ORDER BY p.subject_id"
        case "object":
            return " ORDER BY p.object_id"
        case _ as e:
            raise ValueError(f"invalid ordering: {e}")


def _clauses_from_query(
    query: Query,
) -> tuple[str, dict[str, str]] | None:
    parts = []
    params = {}
    for name in Query.model_fields:
        if (value := getattr(query, name)) is not None:
            if name == "query":
                name = "full"
            if name not in QUERY_TO_CLAUSE:
                raise NotImplementedError(f"query component not implemented: {name}")
            else:
                parts.append(QUERY_TO_CLAUSE[name](value))
                params[name] = value
    if not parts:
        return None
    rv = "WHERE " + " AND ".join(parts)
    return rv, params


QUERY_TO_CLAUSE: dict[str, Callable[[str | bool], str]] = {
    "full": lambda value: (
        "(toLower(p.subject) CONTAINS toLower($full) "
        "OR toLower(p.object) CONTAINS toLower($full)"
        "OR toLower(p.subject_label) CONTAINS toLower($full)"
        "OR toLower(p.object_label) CONTAINS toLower($full)"
        ")"
        # TODO also search over mapping tool name
    ),
    "triple_id": lambda value: "p.triple_id = $triple_id",
    "subject_prefix": lambda value: "p.subject STARTS WITH $subject_prefix",
    "subject_query": lambda value: (
        "(toLower(p.subject) CONTAINS toLower($subject_query) "
        "OR toLower(p.subject_label) CONTAINS toLower($subject_query)"
    ),
    "object_query": lambda value: (
        "(toLower(p.object) CONTAINS toLower($object_query) "
        "OR toLower(p.object_label) CONTAINS toLower($object_query)"
    ),
    "object_prefix": lambda value: "p.object STARTS WITH $object_prefix",
    "prefix": lambda value: "(p.subject STARTS WITH prefix OR p.object STARTS WITH $prefix)",
    # TODO strip weird characters
    "same_text": lambda value: (
        "(p.predicate = 'skos:exactMatch' "
        "AND replace(replace(toLower(p.object_label), '-', ''), ' ', '') "
        "  = replace(replace(toLower(p.subject_label), '-', ''), ' ', ''))"
        if value
        else """(
            p.predicate = 'skos:exactMatch'
            AND (
                p.subject_label IS NULL
                OR p.object_label IS NULL
                OR replace(replace(toLower(p.object_label), '-', ''), ' ', '') <>
                   replace(replace(toLower(p.subject_label), '-', ''), ' ', '')
            )
        )"""
    ),
}


def _get_worker(cypher: LiteralString) -> Callable[Concatenate[neo4j.ManagedTransaction, P], None]:
    def _do_work(tx: neo4j.ManagedTransaction, /, *args: P.args, **kwargs: P.kwargs) -> None:
        tx.run(cypher, *args, **kwargs)

    return _do_work
