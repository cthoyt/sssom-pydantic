"""Mock an API."""

import pathlib

import curies
import flask
from a2wsgi import WSGIMiddleware
from fastapi import FastAPI
from flask_bootstrap import Bootstrap5

from sssom_pydantic.api import SemanticMappingHash
from sssom_pydantic.database import SemanticMappingRepository
from sssom_pydantic.web.router import router

__all__ = [
    "get_app",
]


def get_app(
    *,
    repository: SemanticMappingRepository | None = None,
    semantic_mapping_hash: SemanticMappingHash | None = None,
    converter: curies.Converter | None = None,
    add_examples: bool = False,
    frontend: bool = True,
) -> FastAPI:
    """Get a FastAPI app.

    :param repository: A mapping repository, e.g., a SQL database. If not given,
        initializes an in-memory SQLite database.
    :param semantic_mapping_hash: A function that deterministically hashes a mapping.
        This is required until the SSSOM specification `defines a standard hashing
        procedure <https://github.com/mapping-commons/sssom/issues/436>`_.
    :param converter: A converter. If not given, uses Bioregistry.
    :param add_examples: Add example mappings from
        :data:`sssom_pydantic.examples.EXAMPLE_MAPPINGS`, useful when debugging.
    :param frontend: bool, whether to use a flask-based frontend or not.

    :returns: A FastAPI app

    If you want to write the OpenAPI schema to a JSON file, do the following:

    .. code-block:: python

        app = get_app()
        schema = app.openapi()
    """
    if repository is None:  # pragma: no cover
        import pystow

        from sssom_pydantic.database import SemanticMappingDatabase

        if converter is None:
            import bioregistry

            converter = bioregistry.get_default_converter()

        repository = SemanticMappingDatabase.from_connection(
            connection=pystow.joinpath_sqlite("sssom", name="test.db"),
            semantic_mapping_hash=semantic_mapping_hash,
            converter=converter,
        )

    if add_examples or not repository.count_mappings():
        biomappings_dir = pathlib.Path("/Users/cthoyt/dev/biomappings/src/biomappings/resources/")
        repository.read(biomappings_dir.joinpath("predictions.sssom.tsv"), progress=True)
        repository.read(biomappings_dir.joinpath("positive.sssom.tsv"), progress=True)
        repository.read(biomappings_dir.joinpath("negative.sssom.tsv"), progress=True)

    app = FastAPI(
        title="SSSOM Server",
        description="A database backend for SSSOM records",
    )
    app.state.repository = repository
    app.include_router(router)

    if frontend:
        from sssom_pydantic.web.ui import ui_blueprint

        flask_app = flask.Flask(__name__)
        flask_app.config["repository"] = repository
        Bootstrap5(flask_app)
        flask_app.register_blueprint(ui_blueprint)

    app.mount("/", WSGIMiddleware(flask_app))  # type:ignore

    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(get_app(), host="0.0.0.0", port=8776)  # noqa:S104
