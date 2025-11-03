"""Test the database."""

import unittest

from curies import Triple
from sqlmodel import Session, SQLModel, create_engine, select

from sssom_pydantic.api import SemanticMapping


class TestDatabase(unittest.TestCase):
    """Test SSSOM database."""

    def test_database(self) -> None:
        """Test the database."""
        m1 = SemanticMapping(
            subject="CHEBI:135122",
            predicate="skos:exactMatch",
            object="mesh:C073738",
            justification="semapv:ManualMappingCuration",
        )
        m2 = SemanticMapping(
            subject="CHEBI:135125",
            predicate="skos:exactMatch",
            object="mesh:C073260",
            justification="semapv:ManualMappingCuration",
        )

        engine = create_engine("sqlite://")
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            session.add_all([m1, m2])
            session.commit()

        # Query for edges with a given subject, by string
        with Session(engine) as session:
            statement = select(Triple).where(Triple.subject == "CHEBI:135122")
            session.exec(statement).all()
