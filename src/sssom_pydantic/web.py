"""Mock an API."""

import datetime
import pathlib
from typing import Annotated, TypeAlias, cast

import curies
import fastapi
import flask
from a2wsgi import WSGIMiddleware
from curies import Reference
from curies.vocabulary import charlie, exact_match, manual_mapping_curation
from fastapi import APIRouter, Body, Depends, FastAPI, HTTPException, Path, Request
from flask_bootstrap import Bootstrap5

from sssom_pydantic.api import SemanticMapping, SemanticMappingHash
from sssom_pydantic.database import SemanticMappingRepository
from sssom_pydantic.examples import R1, R2
from sssom_pydantic.process import MARKS, Mark, estimate_confidence
from sssom_pydantic.query import Query

__all__ = [
    "get_app",
    "router",
]

router = APIRouter()


def get_repository(request: Request) -> SemanticMappingRepository:
    """Get the controller from the web app."""
    return cast(SemanticMappingRepository, request.app.state.repository)


#: A type alias for a controller that contains a dependency injection
#: annotation for FastAPI.
AnnotatedRepository: TypeAlias = Annotated[SemanticMappingRepository, Depends(get_repository)]

#: A type alias for a CURIE passed via the path
AnnotatedCURIE = Annotated[str, Path(description="The CURIE for mapping record")]


@router.get("/mapping/", response_model_exclude_unset=True, response_model_exclude_defaults=True)
def get_mappings(
    repository: AnnotatedRepository,
    query: Annotated[Query | None, fastapi.Path(examples=[Query(query="ammeline")])] = None,
    limit: Annotated[int | None, fastapi.Path()] = None,
    offset: Annotated[int | None, fastapi.Path()] = None,
    order_by: Annotated[str | None, fastapi.Path()] = None,
) -> list[SemanticMapping]:
    """Get mappings."""
    return list(repository.get_mappings(query, limit=limit, offset=offset, order_by=order_by))


@router.get(
    "/mapping/{curie}", response_model_exclude_unset=True, response_model_exclude_defaults=True
)
def get_mapping(repository: AnnotatedRepository, curie: AnnotatedCURIE) -> SemanticMapping:
    """Get a mapping by CURIE."""
    mapping = repository.get_mapping(Reference.from_curie(curie))
    if mapping is None:
        raise HTTPException(status_code=404, detail="Mapping not found")
    return mapping


@router.delete("/mapping/{curie}")
def delete_mapping(repository: AnnotatedRepository, curie: AnnotatedCURIE) -> str:
    """Get a mapping by CURIE."""
    repository.delete_mapping(Reference.from_curie(curie))
    return "ok"


@router.post("/mapping/")
def post_mapping(
    repository: AnnotatedRepository,
    mapping: Annotated[
        SemanticMapping,
        Body(
            examples=[
                SemanticMapping(
                    subject=R1,
                    predicate=exact_match,
                    object=R2,
                    justification=manual_mapping_curation,
                    authors=[charlie],
                    mapping_date=datetime.date(2025, 8, 1),
                ),
            ]
        ),
    ],
) -> Reference:
    """Add a mapping by CURIE."""
    return repository.add_mapping(mapping)


# TODO bulk posting mappings (test on scale up to 10k or 100k at a time)


@router.post("/action/publish/{curie}")
def publish_mapping(
    repository: AnnotatedRepository,
    curie: AnnotatedCURIE,
    date: Annotated[
        datetime.date | None,
        fastapi.Query(..., description="The date on which the mapping was published"),
    ] = None,
) -> Reference:
    """Publish a mapping with the given CURIE."""
    return repository.publish(Reference.from_curie(curie), date=date)


@router.post("/action/curate/{curie}")
def curate_mapping(
    repository: AnnotatedRepository,
    curie: AnnotatedCURIE,
    authors: Annotated[list[Reference], Body(..., examples=[charlie])],
    mark: Annotated[Mark, Body(..., examples=list(MARKS))],
) -> Reference:
    """Publish a mapping with the given CURIE."""
    return repository.curate(Reference.from_curie(curie), authors=authors, mark=mark)


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

    if add_examples:
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

    flask_app = flask.Flask(__name__)
    Bootstrap5(flask_app)

    @flask_app.get("/")
    def show_home() -> str:
        """Serve the homepage."""
        query = Query.model_validate(flask.request.args)
        n_mappings = repository.count_mappings(query)
        n_entities = repository.count_entities(query)
        mappings = repository.get_mappings(
            limit=10,
            order_by=flask.request.args.get("order_by"),
        )
        return flask.render_template(
            "home.html",
            repository=repository,
            converter=repository.converter,
            mappings=mappings,
            query=query,
            n_mappings=n_mappings,
            n_entities=n_entities,
        )

    @flask_app.get("/show/triple/<triple_id>")
    def show_triple(triple_id: str) -> str:
        mappings = repository.get_mappings(Query(triple_id=triple_id))
        confidence = estimate_confidence(mappings)
        return flask.render_template(
            "triple.html",
            repository=repository,
            converter=repository.converter,
            triple_id=triple_id,
            mappings=mappings,
            confidence=confidence,
        )

    @flask_app.get("/show/mapping/<curie>")
    def show_mapping(curie: str) -> str:
        reference = Reference.from_curie(curie)
        mapping = repository.get_mapping(reference)
        if mapping is None:
            raise flask.abort(404)
        return flask.render_template(
            "mapping.html",
            repository=repository,
            converter=repository.converter,
            mapping=mapping,
        )

    app.mount("/", WSGIMiddleware(flask_app))

    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(get_app(add_examples=True), host="0.0.0.0", port=8776)  # noqa:S104
