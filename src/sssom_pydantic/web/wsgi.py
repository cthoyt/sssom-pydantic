"""Run a mapping app."""

from sssom_pydantic.web.impl import get_app

app = get_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8776)  # noqa:S104
