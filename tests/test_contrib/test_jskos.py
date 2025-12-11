"""Test JSKOS export."""

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

from curies import Converter, Reference
from curies.vocabulary import exact_match, manual_mapping_curation
from pydantic import BaseModel

import sssom_pydantic
from sssom_pydantic import SemanticMapping
from sssom_pydantic.examples import EXAMPLE_MAPPINGS
from tests.cases import TEST_CONVERTER, TEST_METADATA


@unittest.skipUnless(importlib.util.find_spec("jskos"), reason="requires JSKOS")
class TestJSKOSExport(unittest.TestCase):
    """Test JSKOS export."""

    def assert_model_equal(self, expected: BaseModel, actual: BaseModel) -> None:
        """Assert two models are equal."""
        self.assertEqual(
            expected.model_dump(exclude_none=True, exclude_unset=True),
            actual.model_dump(exclude_unset=True, exclude_none=True),
        )

    def test_jskos(self) -> None:
        """Test JSKOS export."""
        from jskos import Concept

        from sssom_pydantic.contrib.jskos_export import mapping_set_to_jskos

        converter = Converter.from_prefix_map(
            {
                "skos": "http://www.w3.org/2004/02/skos/core#",
                "x": "https://example.org/",
                "semapv": "https://w3id.org/semapv/vocab/",
            }
        )
        license_uri = "https://creativecommons.org/licenses/by/4.0/"
        mapping = SemanticMapping(
            subject=Reference(prefix="x", identifier="1"),
            predicate=exact_match,
            object=Reference(prefix="x", identifier="1"),
            justification=manual_mapping_curation,
        )
        expected_jskos_record = {
            "license": [{"uri": license_uri}],
            "uri": TEST_METADATA.mapping_set_id,
            "mappings": [
                {
                    "type": ["http://www.w3.org/2004/02/skos/core#exactMatch"],
                    "from": {"memberSet": [{"uri": "http://example.org/1"}]},
                    "to": {"memberSet": [{"uri": "http://example.org/2"}]},
                    "justification": "https://w3id.org/semapv/vocab/ManualMappingCuration",
                }
            ],
        }
        expected = Concept.model_validate(expected_jskos_record)
        self.assert_model_equal(
            expected, mapping_set_to_jskos([mapping], converter, TEST_METADATA.process(converter))
        )

    def test_all_jskos(self) -> None:
        """Test converting examples to JSKOS then back."""
        import jskos

        for i, example in enumerate(EXAMPLE_MAPPINGS):
            with self.subTest(i=i), tempfile.TemporaryDirectory() as td:
                tsv_path = Path(td).joinpath("example.sssom.tsv")
                sssom_pydantic.write(
                    [example], tsv_path, metadata=TEST_METADATA, converter=TEST_CONVERTER
                )

                # Convert the SSSOM TSV to JSKOS using the sssom-js package
                # on NPM (https://www.npmjs.com/package/sssom-js)
                jskos_path = Path(td).joinpath("example.sssom.json")
                subprocess.call(  # noqa:S603
                    [  # noqa:S607
                        "npx",
                        "sssom-js",
                        "--from",
                        "csv",
                        "--to",
                        "jskos",
                        "--output",
                        jskos_path.as_posix(),
                        tsv_path.as_posix(),
                    ]
                )
                jskos.read(jskos_path)
