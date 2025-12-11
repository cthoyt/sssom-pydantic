"""Mock an API."""

import datetime
import json
import pathlib
from typing import Annotated, Any, TypeAlias, cast

from curies import Reference
from curies.vocabulary import charlie, exact_match, manual_mapping_curation
from fastapi import APIRouter, Body, Depends, FastAPI, HTTPException, Path, Query, Request

from sssom_pydantic import SemanticMapping
from sssom_pydantic.api import SemanticMappingHash, mapping_hash_v1
from sssom_pydantic.database import SemanticMappingDatabase
from sssom_pydantic.examples import R1, R2

__all__ = [
    "get_app",
    "get_openapi_schema",
    "router",
    "write_openapi_schema",
]

router = APIRouter()


def get_controller(request: Request) -> SemanticMappingDatabase:
    """Get the controller from the web app."""
    return cast(SemanticMappingDatabase, request.app.state.database)


#: A type alias for a controller that contains a dependency injection
#: annotation for FastAPI.
AnnotatedController: TypeAlias = Annotated[SemanticMappingDatabase, Depends(get_controller)]

#: A type alias for a CURIE passed via the path
AnnotatedCURIE = Annotated[str, Path(description="The CURIE for mapping record")]


@router.get("/mapping/{curie}")
def get_mapping(controller: AnnotatedController, curie: AnnotatedCURIE) -> SemanticMapping:
    """Get a mapping by CURIE."""
    mapping = controller.get_mapping(Reference.from_curie(curie))
    if mapping is None:
        raise HTTPException(status_code=404, detail="Mapping not found")
    return mapping.to_semantic_mapping()


@router.delete("/mapping/{curie}")
def delete_mapping(controller: AnnotatedController, curie: AnnotatedCURIE) -> str:
    """Get a mapping by CURIE."""
    controller.delete_mapping(Reference.from_curie(curie))
    return "ok"


@router.post("/mapping/")
def post_mapping(
    controller: AnnotatedController,
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
) -> str:
    """Add a mapping by CURIE."""
    controller.add_mapping(mapping)
    return "ok"


@router.post("/action/publish/{curie}")
def publish_mapping(
    controller: AnnotatedController,
    curie: AnnotatedCURIE,
    date: Annotated[datetime.date | None, Query(...)] = None,
) -> str:
    """Publish a mapping with the given CURIE."""
    controller.publish(Reference.from_curie(curie), date=date)
    return "ok"


@router.post("/action/curate/{curie}")
def curate_mapping(
    controller: AnnotatedController,
    curie: AnnotatedCURIE,
    date: Annotated[datetime.date | None, Query(...)] = None,
) -> str:
    """Publish a mapping with the given CURIE."""
    controller.publish(Reference.from_curie(curie), date=date)
    return "ok"


def get_app(
    *,
    database: SemanticMappingDatabase | None = None,
    semantic_mapping_hash: SemanticMappingHash | None = None,
) -> FastAPI:
    """Get a FastAPI app."""
    if database is None:
        if semantic_mapping_hash is None:
            semantic_mapping_hash = mapping_hash_v1
        database = SemanticMappingDatabase.memory(semantic_mapping_hash=semantic_mapping_hash)
    app = FastAPI()
    app.state.database = database
    app.include_router(router)
    return app


def get_openapi_schema() -> dict[str, Any]:
    """Get the OpenAPI schema."""
    return get_app().openapi()


def write_openapi_schema(path: str | pathlib.Path) -> None:
    """Write the OpenAPI schema."""
    path = pathlib.Path(path).expanduser().resolve()
    path.write_text(json.dumps(get_openapi_schema(), indent=2))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(get_app(), host="0.0.0.0", port=8776)  # noqa:S104
