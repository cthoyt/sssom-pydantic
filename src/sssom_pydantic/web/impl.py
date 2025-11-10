"""Construct a FastAPI app."""

from pathlib import Path
from typing import Any

from fastapi import FastAPI

from .controller import Controller
from .dict_controller import DictController
from .router import router

__all__ = [
    "get_app",
]


def get_app(controller: Controller | None = None) -> FastAPI:
    """Get a FastAPI app."""
    if controller is None:
        controller = DictController()
    app = FastAPI()
    app.state.controller = controller
    app.include_router(router)
    return app


def get_openapi_schema() -> dict[str, Any]:
    """Get the OpenAPI schema."""
    return get_app().openapi()


def write_openapi_schema(path: Path) -> None:
    """Write the OpenAPI schema."""
    import json

    path.write_text(json.dumps(get_openapi_schema(), indent=2))


if __name__ == "__main__":
    write_openapi_schema(Path.home().joinpath("Desktop", "schema.json"))
