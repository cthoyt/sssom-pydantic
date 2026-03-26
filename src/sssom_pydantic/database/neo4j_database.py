"""A Neo4j implementation of a semantic mapping repository."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Sequence
from contextlib import closing
from typing import (
    TYPE_CHECKING,
    Any,
    Concatenate,
    Literal,
    LiteralString,
    ParamSpec,
    TypeVar,
    cast,
    overload,
)

from curies import NamableReference, Reference

from sssom_pydantic.api import SemanticMapping, mapping_hash_v1
from sssom_pydantic.database import SemanticMappingRepository
from sssom_pydantic.examples import EXAMPLE_MAPPINGS
from sssom_pydantic.query import Query

if TYPE_CHECKING:
    import neo4j
    from sqlalchemy.sql.selectable import ColumnExpressionArgument  # type:ignore[attr-defined]

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
    ) -> None:
        """Initialize the client.

        :param uri: The URI of the Neo4j database.
        :param user: The username for the Neo4j database.
        :param password: The password for the Neo4j database.
        """
        import neo4j

        super().__init__()

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

    def _write(self, cypher: LiteralString, *args: P.args, **kwargs: P.kwargs) -> None:
        with closing(self.driver.session()) as session:
            session.execute_write(_get_worker(cypher), *args, **kwargs)

    def add_mappings(self, mappings: Iterable[SemanticMapping]) -> list[Reference]:
        """Add mappings to the database."""
        cypher: LiteralString = """
            UNWIND $batch AS row
            MERGE (subject:Entity {curie: row.subject})
              SET subject.name = row.subject_label
            MERGE (object:Entity {curie: row.object})
              SET object.name = row.object_label
            WITH subject, object, row
            MERGE (m:SemanticMapping {id: row.id})
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
        for mapping in mappings:
            reference = self.hash_mapping(mapping)
            references.append(reference)
            batch.append(
                {
                    "id": reference.identifier,
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

    def hash_mapping(self, mapping: SemanticMapping) -> Reference:
        """Hash a mapping."""
        return mapping_hash_v1(mapping)

    def count_mappings(
        self, where_clauses: Query | list[ColumnExpressionArgument[bool]] | None = None
    ) -> int:
        """Count the mappings in the database."""

        def _count_nodes(tx: neo4j.ManagedTransaction) -> int:
            result = tx.run("MATCH (n:SemanticMapping) RETURN count(n) AS total")
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
            raise ValueError
        else:
            return None

    def get_mappings(
        self,
        where_clauses: Query | list[ColumnExpressionArgument[bool]] | None = None,
        limit: int | None = None,
        offset: int | None = None,
        order_by: ColumnExpressionArgument[Any] | list[ColumnExpressionArgument[Any]] | None = None,
    ) -> Sequence[SemanticMapping]:
        """Get mappings."""

        def _get_nodes(tx: neo4j.ManagedTransaction, uids: list[str]) -> list[dict[str, Any]]:
            result = tx.run(
                "MATCH (p:SemanticMapping) WHERE p.id IN $uids RETURN p",
                uids=uids,
            )
            return [record["p"] for record in result]

        raise NotImplementedError("need to have a query building functionality for cypher")
        with self.driver.session(database="neo4j") as session:
            nodes = session.execute_read(_get_nodes, ...)
            return [self._from_data(node) for node in nodes]

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


def _get_worker(cypher: LiteralString) -> Callable[Concatenate[neo4j.ManagedTransaction, P], None]:
    def _do_work(tx: neo4j.ManagedTransaction, /, *args: P.args, **kwargs: P.kwargs) -> None:
        tx.run(cypher, *args, **kwargs)

    return _do_work


def _main() -> None:
    db = Neo4jSemanticMappingRepository(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="neo4jneo4j",  # noqa:S106,
    )
    db.drop_all()
    if db.count_mappings():
        raise ValueError("mappings exist!")

    db.add_mapping(EXAMPLE_MAPPINGS[0])
    if db.count_mappings() != 1:
        raise ValueError("failed to add mapping properly")

    db.add_mappings(EXAMPLE_MAPPINGS)


if __name__ == "__main__":
    _main()
