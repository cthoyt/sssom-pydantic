"""Mock an API."""

import datetime
from typing import Annotated, TypeAlias, cast

from curies import Reference
from curies.vocabulary import charlie, exact_match, manual_mapping_curation
from fastapi import APIRouter, Body, Depends, FastAPI, HTTPException, Path, Query, Request

from sssom_pydantic import SemanticMapping
from sssom_pydantic.api import SemanticMappingHash, mapping_hash_v1
from sssom_pydantic.database import SemanticMappingRepository
from sssom_pydantic.examples import R1, R2
from sssom_pydantic.process import MARKS, Mark

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


@router.get("/mapping/{curie}")
def get_mapping(repository: AnnotatedRepository, curie: AnnotatedCURIE) -> SemanticMapping:
    """Get a mapping by CURIE."""
    mapping = repository.get_mapping(Reference.from_curie(curie))
    if mapping is None:
        raise HTTPException(status_code=404, detail="Mapping not found")
    return mapping.to_semantic_mapping()


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
                ),
            ]
        ),
    ],
) -> Reference:
    """Add a mapping by CURIE."""
    return repository.add_mapping(mapping)


@router.post("/action/publish/{curie}")
def publish_mapping(
    repository: AnnotatedRepository,
    curie: AnnotatedCURIE,
    date: Annotated[
        datetime.date | None, Query(..., description="The date on which the mapping was published")
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
) -> FastAPI:
    """Get a FastAPI app.

    :param repository: A mapping repository, e.g., a SQL database. If not given,
        initializes an in-memory SQLite database.
    :param semantic_mapping_hash: A function that deterministically hashes a mapping.
        This is required until the SSSOM specification `defines a standard hashing
        procedure <https://github.com/mapping-commons/sssom/issues/436>`_.

    :returns: A FastAPI app

    If you want to write the OpenAPI schema to a JSON file, do the following:

    .. code-block:: python

        app = get_app()
        schema = app.openapi()
    """
    if repository is None:
        from sssom_pydantic.database import SQLSemanticMappingRepository

        repository = SQLSemanticMappingRepository.memory(
            semantic_mapping_hash=semantic_mapping_hash or mapping_hash_v1
        )
    app = FastAPI()
    app.state.repository = repository
    app.include_router(router)
    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(get_app(), host="0.0.0.0", port=8776)  # noqa:S104
