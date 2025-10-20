from typing import Annotated

from curies import Reference
from fastapi import APIRouter, Depends, FastAPI, Request

from sssom_pydantic import SemanticMapping

router = APIRouter()


class Controller:
    def get_by_record_id(self, record: Reference) -> SemanticMapping:
        pass


def get_controller(request: Request) -> Controller:
    return request.app.state.controller


@router.get("/mapping/{curie}")
def get(controller: Annotated[Controller, Depends], curie: str) -> SemanticMapping:
    return controller.get_by_record_id(Reference.from_curie(curie))


def get_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.state.controller = Controller()
    return app
