"""Utilities for parsing a Mapping Commons server and reporting on its results.

A Mapping Commons server is a two-tiered registry. The server's configuration points to
multiple external registries which themselves list various SSSOM artifacts. The
`flagship Mapping Commons server <https://mapping-commons.github.io>`_ is defined with
`this YAML
<https://github.com/mapping-commons/mapping-commons.github.io/raw/refs/heads/main/mapping-server.yml>`_.
It references registries from the `Monarch Initiative
<https://raw.githubusercontent.com/monarch-initiative/monarch-mapping-commons/main/registry.yml>`_,
`Biopragmatics
<https://github.com/biopragmatics/mapping-registry/raw/refs/heads/main/registry.yml>`_,
`Critical Path Institute
<https://gitlab.c-path.org/c-pathontology/mapping-commons/-/raw/main/registry.yml>`_,
and others.

This module implements a workflow that can parse any Mapping Commons server definition
with :func:`get_server`. The result can optionally be _hydrated_ with
:meth:`Server.hydrate` to download and parse the results.

The command line interface for this module parses the flagship Mapping Commons server
that's hosted at https://mapping-commons.github.io and whose definition is available
`here
<https://github.com/mapping-commons/mh_mapping_initiative/raw/refs/heads/master/registry.yml>`_.

.. code-block:: console

    $ python -m sssom_pydantic.contrib.mapping_commons_registry
"""

import hashlib
import logging
from collections import Counter
from pathlib import Path
from typing import Annotated, Self

import click
import pystow
from pydantic import AnyUrl, BaseModel, ConfigDict, Field
from pystow.utils import name_from_url
from pystow.utils.pydantic_utils import read_pydantic_yaml
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

import sssom_pydantic
from sssom_pydantic import MappingSet, SemanticMapping
from sssom_pydantic.io import ParseError, _get_exc

logger = logging.getLogger(__name__)

SERVER_EXAMPLE = "https://github.com/mapping-commons/mapping-commons.github.io/raw/refs/heads/main/mapping-server.yml"
REGISTRY_EXAMPLE = (
    "https://github.com/mapping-commons/mh_mapping_initiative/raw/refs/heads/master/registry.yml"
)
SKIPS_REGISTRIES = {
    # broken, see https://github.com/mapping-commons/mesh-mappings/pull/4
    "https://raw.githubusercontent.com/mapping-commons/mesh-mappings/main/mappings.yml",
    # text mappings aren't handled by sssom-pydantic
    "https://raw.githubusercontent.com/mapping-commons/ebi-text-mappings/refs/heads/main/mappings.yml",
}
SKIP_SSSOM = {"http://w3id.org/sssom/commons/monarch/mappings/mondo_hp_lexical.sssom.tsv"}

MODULE = pystow.module("sssom", "mapping-commons")


def _get_path(url: AnyUrl, *, code: str, name: str | None, force: bool = False) -> Path:
    url_str = str(url)
    if name is None:
        # do this in case of duplicate file names within a given registry
        md5 = hashlib.md5(usedforsecurity=False)
        md5.update(url_str.encode("utf-8"))
        name = md5.hexdigest()[:6] + "-" + name_from_url(url_str)
    path = MODULE.ensure(code, url=url_str, name=name, force=force)
    return path


class MappingSetReference(BaseModel):
    """Represents metadata about a mapping set.

    .. seealso::

        https://mapping-commons.github.io/sssom/MappingSetReference/
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    url: Annotated[AnyUrl, Field(alias="mapping_set_id")]
    group: Annotated[str, Field(alias="mapping_set_group")]
    confidence: Annotated[float | None, Field(alias="registry_confidence")] = None
    local_name: str | None = None

    mapping_set: Annotated[MappingSet | None, Field(exclude=True)] = None
    mappings: Annotated[list[SemanticMapping] | None, Field(repr=False, exclude=True)] = None
    errors: Annotated[list[ParseError] | None, Field(None, repr=False, exclude=True)] = None

    def hydrate(self, *, code: str, force: bool = False) -> None:
        """Hydrate the mappings and metadata from this mapping set."""
        if str(self.url) in SKIP_SSSOM:
            return
        try:
            with logging_redirect_tqdm():
                path = _get_path(self.url, code=code, name=self.local_name, force=force)
                self.mappings, _converter, self.mapping_set, self.errors = sssom_pydantic.read(
                    path,
                    return_errors=True,
                    progress=True,
                    progress_kwargs={"leave": False},
                )
        except Exception as e:  # noqa:BLE001
            tqdm.write(click.style(f"\n{self.url} uncaught exception in {e}\n", fg="red"))
        else:
            if self.mappings:
                label = str(self.url)
                if self.mapping_set is not None and self.mapping_set.title is not None:
                    label += f" ({self.mapping_set.title})"
                elif self.local_name:
                    label += f" ({self.local_name})"
                tqdm.write(click.style(f"{label} had {len(self.mappings):,} mappings", fg="green"))
            if self.errors:
                error_path = path.with_suffix(".error.txt")
                tqdm.write(
                    click.style(
                        f"{self.url} had {len(self.errors):,} errors. See {error_path}", fg="yellow"
                    )
                )
                with error_path.open(mode="w") as error_file:
                    for error in self.errors[:5]:
                        tqdm.write(
                            f"Error on {error.line_number}:\n{_get_exc(error.exception)}\n",
                            file=error_file,
                        )


class Registry(BaseModel):
    """Represents full metadata about a registry.

    .. seealso::

        https://mapping-commons.github.io/sssom/MappingRegistry/
    """

    iri: AnyUrl = Field(..., alias="mapping_registry_id")
    title: str | None = Field(None, alias="registry_title")
    description: str | None = Field(None, alias="registry_description")
    homepage: AnyUrl | None = None  # weirdly, not part of the SSSOM schema
    documentation: AnyUrl | None = None  # weirdly, not part of the SSSOM schema
    mapping_set_references: list[MappingSetReference]

    def hydrate(self, *, code: str, force: bool = False) -> None:
        """Hydrate the mappings and metadata for each mapping set."""
        counter = Counter(
            name_from_url(str(mapping_set_ref.url))
            for mapping_set_ref in self.mapping_set_references
            if mapping_set_ref.local_name is None
        )
        counter = Counter({k: count for k, count in counter.items() if count > 1})
        if counter:
            raise ValueError(f"registry has duplicate names w/o using local names: {classmethod}")
        for mapping_set_ref in tqdm(
            self.mapping_set_references,
            desc=f"Hydrating registry {self.iri}",
            unit="mapping set",
            leave=False,
        ):
            mapping_set_ref.hydrate(code=code, force=force)

    # TODO remove description if doubles title


class ServerEntry(BaseModel):
    """Represents minimum metadata about a registry indexed by a server."""

    code: str = Field(
        ...,
        alias="id",
        description="This is a code for the resource, local to the mapping server configuration",
    )
    url: AnyUrl = Field(..., alias="url")
    registry: Registry | None = None

    def hydrate(self, *, force: bool = False) -> None:
        """Hydrate metadata about this registry."""
        if str(self.url) in SKIPS_REGISTRIES:
            pass  # too broken
        elif self.registry is None:
            try:
                self.registry = get_registry(str(self.url))
            except ValueError as e:
                tqdm.write(
                    click.style(f"{self.url} failed to parse registry\n\n{_get_exc(e)}", fg="red")
                )
            else:
                #  does code need normalization?
                self.registry.hydrate(code=self.code, force=force)


class Server(BaseModel):
    """Represents metadata about a Mapping Server."""

    iri: AnyUrl
    title: str
    registries: list[ServerEntry]

    def hydrate(self, *, force: bool = False) -> Self:
        """Hydrate metadata about this server's registries."""
        for registry in tqdm(
            self.registries, desc="Hydrating server", unit="registry", leave=False
        ):
            registry.hydrate(force=force)
        return self


def get_registry(url: str) -> Registry:
    """Get metadata about a registry from a URL."""
    return read_pydantic_yaml(url, Registry)


def get_server(url: str) -> Server:
    """Get metadata about a server from a URL."""
    path = MODULE.ensure(url=url, force=True)
    return read_pydantic_yaml(path, Server)


@click.command()
@click.option("--url", default=SERVER_EXAMPLE, show_default=True)
@click.option("--force", is_flag=True)
def _main(url: str, force: bool) -> None:
    """Parse and report on a Mapping Commons server."""
    server = get_server(url)
    server.hydrate(force=force)


if __name__ == "__main__":
    _main()
