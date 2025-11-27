"""Mock an API."""

from typing import Annotated, cast

from curies import Reference
from fastapi import APIRouter, Depends, FastAPI, Request

from sssom_pydantic import SemanticMapping

router = APIRouter()


class Controller:
    """A controller."""

    def get_by_record_id(self, record: Reference) -> SemanticMapping:
        """Get a semantic mapping by reference."""
        raise NotImplementedError


def get_controller(request: Request) -> Controller:
    """Get the controller from the web app."""
    return cast(Controller, request.app.state.controller)


@router.get("/mapping/{curie}")
def get(controller: Annotated[Controller, Depends(get_controller)], curie: str) -> SemanticMapping:
    """Get a mapping by CURIE."""
    return controller.get_by_record_id(Reference.from_curie(curie))


def get_app() -> FastAPI:
    """Get a FastAPI app."""
    app = FastAPI()
    app.include_router(router)
    app.state.controller = Controller()
    return app
