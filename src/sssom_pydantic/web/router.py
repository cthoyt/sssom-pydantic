"""Mock an API."""

import datetime
from typing import Annotated, TypeAlias, cast

from curies import Reference
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from sssom_pydantic import SemanticMapping
from sssom_pydantic.database import SemanticMappingDatabase

__all__ = [
    "router",
]

router = APIRouter()


def get_controller(request: Request) -> SemanticMappingDatabase:
    """Get the controller from the web app."""
    return cast(SemanticMappingDatabase, request.app.state.database)


#: A type alias for a controller that contains a dependency injection
#: annotation for FastAPI.
AnnotatedController: TypeAlias = Annotated[SemanticMappingDatabase, Depends(get_controller)]


@router.get("/mapping/{curie}")
def get_mapping(controller: AnnotatedController, curie: str) -> SemanticMapping:
    """Get a mapping by CURIE."""
    mapping = controller.get_mapping(Reference.from_curie(curie))
    if mapping is None:
        raise HTTPException(status_code=404, detail="Mapping not found")
    return mapping.to_semantic_mapping()


@router.delete("/mapping/{curie}")
def delete_mapping(controller: AnnotatedController, curie: str) -> str:
    """Get a mapping by CURIE."""
    controller.delete_mapping(Reference.from_curie(curie))
    return "ok"


@router.post("/mapping/")
def post_mapping(controller: AnnotatedController, mapping: SemanticMapping) -> str:
    """Add a mapping by CURIE."""
    controller.add_mapping(mapping)
    return "ok"


@router.post("/action/publish/{curie}")
def publish_mapping(
    controller: AnnotatedController,
    curie: str,
    date: Annotated[datetime.date | None, Query(...)] = None,
) -> str:
    """Publish a mapping with the given CURIE."""
    controller.publish(Reference.from_curie(curie), date=date)
    return "ok"


@router.post("/action/publish/{curie}")
def curate_mapping(
    controller: AnnotatedController,
    curie: str,
    date: Annotated[datetime.date | None, Query(...)] = None,
) -> str:
    """Publish a mapping with the given CURIE."""
    controller.publish(Reference.from_curie(curie), date=date)
    return "ok"
