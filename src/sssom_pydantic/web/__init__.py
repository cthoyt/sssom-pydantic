"""Mock an API."""

import curies
from fastapi import FastAPI

from sssom_pydantic.api import SemanticMappingHash
from sssom_pydantic.database import SemanticMappingRepository
from sssom_pydantic.examples import EXAMPLE_MAPPINGS
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
) -> FastAPI:
    """Get a FastAPI app.

    :param repository: A mapping repository, e.g., a SQL database. If not given,
        initializes an in-memory SQLite database.
    :param semantic_mapping_hash: A function that deterministically hashes a mapping.
        This is required until the SSSOM specification `defines a standard hashing
        procedure <https://github.com/mapping-commons/sssom/issues/436>`_.
    :param add_examples: Add example mappings from
        :data:`sssom_pydantic.examples.EXAMPLE_MAPPINGS`, useful when debugging.

    :returns: A FastAPI app

    If you want to write the OpenAPI schema to a JSON file, do the following:

    .. code-block:: python

        app = get_app()
        schema = app.openapi()
    """
    if repository is None:  # pragma: no cover
        from sssom_pydantic.database import SemanticMappingDatabase

        if converter is None:
            import bioregistry

            converter = bioregistry.get_default_converter()

        repository = SemanticMappingDatabase.memory(
            semantic_mapping_hash=semantic_mapping_hash,
            converter=converter,
        )

    if add_examples:
        repository.add_mappings(EXAMPLE_MAPPINGS)

    app = FastAPI(
        title="SSSOM Server",
        description="A database backend for SSSOM records",
    )
    app.state.repository = repository
    app.include_router(router)
    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(get_app(), host="0.0.0.0", port=8776)  # noqa:S104
