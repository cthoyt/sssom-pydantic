"""Mock an API."""

import datetime
from typing import Annotated, TypeAlias, cast

from curies import Reference
from curies.vocabulary import charlie, exact_match, manual_mapping_curation
from fastapi import APIRouter, Body, Depends, FastAPI, HTTPException, Path, Query, Request

from sssom_pydantic import SemanticMapping
from sssom_pydantic.api import SemanticMappingHash, mapping_hash_v1
from sssom_pydantic.database import SemanticMappingDatabase
from sssom_pydantic.examples import R1, R2
from sssom_pydantic.process import MARKS, Mark

__all__ = [
    "get_app",
    "router",
]

router = APIRouter()


def get_controller(request: Request) -> SemanticMappingDatabase:
    """Get the controller from the web app."""
    return cast(SemanticMappingDatabase, request.app.state.database)


#: A type alias for a controller that contains a dependency injection
#: annotation for FastAPI.
AnnotatedDatabase: TypeAlias = Annotated[SemanticMappingDatabase, Depends(get_controller)]

#: A type alias for a CURIE passed via the path
AnnotatedCURIE = Annotated[str, Path(description="The CURIE for mapping record")]


@router.get("/mapping/{curie}")
def get_mapping(controller: AnnotatedDatabase, curie: AnnotatedCURIE) -> SemanticMapping:
    """Get a mapping by CURIE."""
    mapping = controller.get_mapping(Reference.from_curie(curie))
    if mapping is None:
        raise HTTPException(status_code=404, detail="Mapping not found")
    return mapping.to_semantic_mapping()


@router.delete("/mapping/{curie}")
def delete_mapping(controller: AnnotatedDatabase, curie: AnnotatedCURIE) -> str:
    """Get a mapping by CURIE."""
    controller.delete_mapping(Reference.from_curie(curie))
    return "ok"


@router.post("/mapping/")
def post_mapping(
    database: AnnotatedDatabase,
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
    return database.add_mapping(mapping)


@router.post("/action/publish/{curie}")
def publish_mapping(
    database: AnnotatedDatabase,
    curie: AnnotatedCURIE,
    date: Annotated[
        datetime.date | None, Query(..., description="The date on which the mapping was published")
    ] = None,
) -> Reference:
    """Publish a mapping with the given CURIE."""
    return database.publish(Reference.from_curie(curie), date=date)


@router.post("/action/curate/{curie}")
def curate_mapping(
    database: AnnotatedDatabase,
    curie: AnnotatedCURIE,
    authors: Annotated[list[Reference], Body(..., examples=[charlie])],
    mark: Annotated[Mark, Body(..., examples=list(MARKS))],
) -> Reference:
    """Publish a mapping with the given CURIE."""
    return database.curate(Reference.from_curie(curie), authors=authors, mark=mark)


def get_app(
    *,
    database: SemanticMappingDatabase | None = None,
    semantic_mapping_hash: SemanticMappingHash | None = None,
) -> FastAPI:
    """Get a FastAPI app.

    :param database: A mapping database
    :param semantic_mapping_hash: A function that deterministically hashes a mapping.
        This is required until the SSSOM specification
        `defines a standard hashing procedure <https://github.com/mapping-commons/sssom/issues/436>`_.
    :returns: A FastAPI app

    If you want to write the OpenAPI schema to a JSON file, do the following:

    .. code-block:: python

        app = get_app()
        schema = app.openapi()
    """
    if database is None:
        database = SemanticMappingDatabase.memory(
            semantic_mapping_hash=semantic_mapping_hash or mapping_hash_v1
        )
    app = FastAPI()
    app.state.database = database
    app.include_router(router)
    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(get_app(), host="0.0.0.0", port=8776)  # noqa:S104
