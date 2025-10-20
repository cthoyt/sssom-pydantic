"""Test the database."""

import unittest

from sqlmodel import Session, SQLModel, create_engine, select
from curies import Triple


class TestDatabase(unittest.TestCase):
    """Test SSSOM database."""

    def test_database(self) -> None:
        """Test the database."""
        # m1 = _m()
        # m2 = _m(authors=[charlie])

        m1 = Triple(subject="CHEBI:135122", predicate="skos:exactMatch", object="mesh:C073738")
        m2 = Triple(subject="CHEBI:135125", predicate="skos:exactMatch", object="mesh:C073260")

        engine = create_engine("sqlite://")
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            session.add_all([m1, m2])
            session.commit()

        # Query for edges with a given subject, by string
        with Session(engine) as session:
            statement = select(Triple).where(Triple.subject == "CHEBI:135122")
            session.exec(statement).all()
