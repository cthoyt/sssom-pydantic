"""Test importing BridgeDB."""

from pathlib import Path
import unittest

from sssom_pydantic.contrib.bridgedb_duckdb import _from_bridgedb_v3, _from_bridgedb_v4

HERE = Path(__file__).parent.resolve()
V3_PATH = HERE.joinpath("aminoacids_duckdb_db3.bridge")
V4_PATH = HERE.joinpath("aminoacids_duckdb_db4.bridge")


class TestImportBridgeDb(unittest.TestCase):
    """Test importing BridgeDB."""

    def test_v3(self) -> None:
        mappings = _from_bridgedb_v3(V3_PATH)

    def test_v4(self) -> None:
        mappings = _from_bridgedb_v4(V4_PATH)
