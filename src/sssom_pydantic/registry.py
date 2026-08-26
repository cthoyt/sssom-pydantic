"""Utilities for working with Mapping Servers and Mapping Registries."""

import hashlib
import logging
from pathlib import Path

import click
import pystow
from pydantic import AnyUrl, BaseModel, ConfigDict, Field
from pystow.utils.pydantic_utils import read_pydantic_yaml
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
from typing_extensions import Self

import sssom_pydantic
from sssom_pydantic import MappingSet, SemanticMapping
from sssom_pydantic.io import ParseError, _get_exc

logger = logging.getLogger(__name__)

SERVER_EXAMPLE = "https://github.com/mapping-commons/mapping-commons.github.io/raw/refs/heads/main/mapping-server.yml"
REGISTRY_EXAMPLE = (
    "https://github.com/mapping-commons/mh_mapping_initiative/raw/refs/heads/master/registry.yml"
)
SKIPS_REGISTRIES = {
    "https://raw.githubusercontent.com/mapping-commons/mesh-mappings/main/mappings.yml"
}


def _get_path(url: AnyUrl) -> Path:
    md5 = hashlib.md5(usedforsecurity=False)
    md5.update(str(url).encode("utf-8"))
    path = pystow.ensure("tmp", url=str(url), name=md5.hexdigest())
    return path


class MappingSetReference(BaseModel):
    """Represents metadata about a mapping set.

    .. seealso:: https://mapping-commons.github.io/sssom/MappingSetReference/
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    url: AnyUrl = Field(..., alias="mapping_set_id")
    group: str = Field(..., alias="mapping_set_group")
    confidence: float | None = Field(None, alias="registry_confidence")
    local_name: str | None = None

    mapping_set: MappingSet | None = Field(None, exclude=True)
    mappings: list[SemanticMapping] | None = Field(None, repr=False, exclude=True)
    errors: list[ParseError] | None = Field(None, repr=False, exclude=True)

    def hydrate(self) -> None:
        """Hydrate the mappings and metadata from this mapping set."""
        try:
            with logging_redirect_tqdm():
                self.mappings, _converter, self.mapping_set, self.errors = sssom_pydantic.read(
                    _get_path(self.url),
                    return_errors=True,
                    progress=True,
                    progress_kwargs={"leave": False},
                )
        except Exception as e:
            tqdm.write(click.style(f"\n{self.url} uncaught exception in {e}\n", fg="red"))
        else:
            if self.mappings:
                tqdm.write(
                    click.style(f"{self.url} had {len(self.mappings):,} mappings", fg="green")
                )
            if self.errors:
                tqdm.write(
                    click.style(
                        f"{self.url} had {len(self.errors):,} errors. Sampling:", fg="yellow"
                    )
                )
                for error in self.errors[:5]:
                    tqdm.write(f"Error on {error.line_number}:\n{_get_exc(error.exception)}\n")


class Registry(BaseModel):
    """Represents full metadata about a registry.

    .. seealso:: https://mapping-commons.github.io/sssom/MappingRegistry/
    """

    iri: AnyUrl = Field(..., alias="mapping_registry_id")
    title: str | None = Field(None, alias="registry_title")
    description: str | None = Field(None, alias="registry_description")
    homepage: AnyUrl | None = None  # weirdly, not part of the SSSOM schema
    documentation: AnyUrl | None = None  # weirdly, not part of the SSSOM schema
    mapping_set_references: list[MappingSetReference]

    def hydrate(self) -> None:
        """Hydrate the mappings and metadata for each mapping set."""
        for mapping_set_ref in tqdm(
            self.mapping_set_references,
            desc=f"Hydrating registry {self.iri}",
            unit="mapping set",
            leave=False,
        ):
            mapping_set_ref.hydrate()

    # TODO remove description if doubles title


class ServerEntry(BaseModel):
    """Represents minimum metadata about a registry indexed by a server."""

    code: str = Field(
        ...,
        alias="id",
        description="This is a code for the resource, local to the mapping server configuration",
    )
    url: AnyUrl = Field(..., alias="uri")
    registry: Registry | None = None

    def hydrate(self) -> None:
        """Hydrate metadata about this registry."""
        if str(self.url) in SKIPS_REGISTRIES:
            pass  # too broken
        elif self.registry is None:
            try:
                self.registry = get_registry(str(self.url))
            except ValueError as e:
                tqdm.write(
                    click.style(f"{self.url} failed to parse registry\n{_get_exc(e)}", fg="red")
                )

            else:
                self.registry.hydrate()


class Server(BaseModel):
    """Represents metadata about a Mapping Server."""

    iri: AnyUrl
    title: str
    registries: list[ServerEntry]

    def hydrate(self) -> Self:
        """Hydrate metadata about this server's registries."""
        for registry in tqdm(self.registries, desc="Hydrating server", unit="registry"):
            registry.hydrate()
        return self


def get_registry(url: str) -> Registry:
    """Get metadata about a registry from a URL."""
    return read_pydantic_yaml(url, Registry)


def get_server(url: str) -> Server:
    """Get metadata about a server from a URL."""
    return read_pydantic_yaml(url, Server)


def _main() -> None:
    server = get_server(SERVER_EXAMPLE)
    server.hydrate()


if __name__ == "__main__":
    _main()
