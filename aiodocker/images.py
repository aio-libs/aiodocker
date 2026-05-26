from __future__ import annotations

import io
import json
import warnings
from collections.abc import AsyncIterator, Mapping
from typing import (
    TYPE_CHECKING,
    Any,
    List,
    Literal,
    overload,
)

import aiohttp

from .jsonstream import json_stream_list, json_stream_stream
from .types import SENTINEL, JSONObject, Sentinel, SupportsRead
from .utils import clean_filters, clean_map, compose_auth_header


if TYPE_CHECKING:
    from .docker import Docker


def _has_embedded_tag_or_digest(image_ref: str) -> bool:
    last_segment = image_ref.rsplit("/", 1)[-1]
    return ":" in last_segment or "@" in last_segment


class DockerImages:
    def __init__(self, docker: Docker) -> None:
        self.docker = docker

    async def list(
        self,
        *,
        filters: Mapping[str, Any] | str | None = None,
        **params,
    ) -> List[Any]:
        """
        List of images

        Args:
            filters: Filter expressions for the listing. Accepts a mapping
                like ``{"dangling": ["true"]}``, ``{"label": ["foo=bar"]}``,
                or ``{"reference": ["busybox"]}``. A pre-encoded JSON string
                is also accepted for backwards compatibility, but is
                deprecated and will be removed in 1.0.
            **params: Additional query parameters forwarded to
                ``GET /images/json`` (e.g. ``all``, ``digests``,
                ``shared_size``).
        """
        if filters is not None:
            if isinstance(filters, str):
                warnings.warn(
                    "Passing `filters` as a pre-encoded JSON string is "
                    "deprecated and will be removed in 1.0. Pass a mapping "
                    "such as {'dangling': ['true']} instead.",
                    DeprecationWarning,
                    stacklevel=2,
                )
                params["filters"] = filters
            else:
                params["filters"] = clean_filters(filters)
        response = await self.docker._query_json("images/json", "GET", params=params)
        return response

    async def inspect(self, name: str) -> dict[str, Any]:
        """
        Return low-level information about an image

        Args:
            name: name of the image
        """
        response = await self.docker._query_json(f"images/{name}/json")
        return response

    async def get(self, name: str) -> dict[str, Any]:
        warnings.warn(
            """images.get is deprecated and will be removed in the next release,
            please use images.inspect instead.""",
            DeprecationWarning,
            stacklevel=2,
        )
        return await self.inspect(name)

    async def history(self, name: str) -> dict[str, Any]:
        response = await self.docker._query_json(f"images/{name}/history")
        return response

    @overload
    async def pull(
        self,
        from_image: str,
        *,
        auth: JSONObject | str | bytes | None = None,
        tag: str | None = None,
        repo: str | None = None,
        platform: str | None = None,
        stream: Literal[False] = False,
        timeout: float | Sentinel | None = SENTINEL,
    ) -> List[dict[str, Any]]: ...

    @overload
    def pull(
        self,
        from_image: str,
        *,
        auth: JSONObject | str | bytes | None = None,
        tag: str | None = None,
        repo: str | None = None,
        platform: str | None = None,
        stream: Literal[True],
        timeout: float | Sentinel | None = SENTINEL,
    ) -> AsyncIterator[dict[str, Any]]: ...

    def pull(
        self,
        from_image: str,
        *,
        auth: JSONObject | str | bytes | None = None,
        tag: str | None = None,
        repo: str | None = None,
        platform: str | None = None,
        stream: bool = False,
        timeout: float | Sentinel | None = SENTINEL,
    ) -> Any:
        """
        Similar to `docker pull`, pull an image locally

        Args:
            fromImage: name of the image to pull, optionally including a tag
                       (``name:tag``) or digest (``name@sha256:...``)
            repo: repository name given to an image when it is imported
            tag: tag to pull. When omitted and ``from_image`` does not embed
                 a tag (``name:tag``) or digest (``name@sha256:...``),
                 defaults to ``"latest"`` to match the behavior of the
                 ``docker pull`` CLI. Pass an empty string explicitly to
                 request the Docker Engine's "pull all tags" behavior. To
                 pull by digest, embed it in ``from_image``.
            platform: platform in the format `os[/arch[/variant]]`
            auth: special {'auth': base64} pull private repo

        Raises:
            DockerStreamError: If the Docker Engine reports an error in
                the progress stream (e.g. the registry rejected the pull
                with ``403 Forbidden``). Subclass of ``DockerError``.
        """
        image = from_image  # TODO: clean up
        params = {"fromImage": image}
        headers = {}
        if repo:
            params["repo"] = repo
        if tag is None and not _has_embedded_tag_or_digest(image):
            tag = "latest"
        if tag:
            params["tag"] = tag
        if platform:
            params["platform"] = platform
        if auth is not None:
            registry, has_registry_host, _ = image.partition("/")
            if not has_registry_host:
                raise ValueError(
                    "Image should have registry host when auth information is provided"
                )
            # TODO: assert registry == repo?
            headers["X-Registry-Auth"] = compose_auth_header(auth, registry)

        # Default to infinite timeout for pull operations
        timeout_config = self.docker._resolve_long_running_timeout(timeout)

        cm = self.docker._query(
            "images/create",
            "POST",
            params=params,
            headers=headers,
            timeout=timeout_config,
        )
        return self._handle_response(cm, stream)

    def _handle_response(self, cm, stream):
        if stream:
            return self._handle_stream(cm)
        else:
            return self._handle_list(cm)

    async def _handle_stream(self, cm):
        async with cm as response:
            async for item in json_stream_stream(response):
                yield item

    async def _handle_list(self, cm):
        async with cm as response:
            return await json_stream_list(response)

    @overload
    async def push(
        self,
        name: str,
        *,
        auth: JSONObject | str | bytes | None = None,
        tag: str | None = None,
        stream: Literal[False] = False,
        timeout: float | Sentinel | None = SENTINEL,
    ) -> List[dict[str, Any]]: ...

    @overload
    def push(
        self,
        name: str,
        *,
        auth: JSONObject | str | bytes | None = None,
        tag: str | None = None,
        stream: Literal[True],
        timeout: float | Sentinel | None = SENTINEL,
    ) -> AsyncIterator[dict[str, Any]]: ...

    def push(
        self,
        name: str,
        *,
        auth: JSONObject | str | bytes | None = None,
        tag: str | None = None,
        stream: bool = False,
        timeout: float | Sentinel | None = SENTINEL,
    ) -> Any:
        """
        Similar to ``docker push``, push an image to a registry.

        Raises:
            DockerStreamError: If the Docker Engine reports an error in
                the progress stream (e.g. the registry rejected the push
                with ``403 Forbidden``). Subclass of ``DockerError``.
        """
        params = {}
        headers = {
            # Anonymous push requires a dummy auth header.
            "X-Registry-Auth": "placeholder"
        }
        if tag:
            params["tag"] = tag
        if auth is not None:
            registry, has_registry_host, _ = name.partition("/")
            if not has_registry_host:
                raise ValueError(
                    "Image should have registry host when auth information is provided"
                )
            headers["X-Registry-Auth"] = compose_auth_header(auth, registry)

        # Default to infinite timeout for push operations
        timeout_config = self.docker._resolve_long_running_timeout(timeout)

        cm = self.docker._query(
            f"images/{name}/push",
            "POST",
            params=params,
            headers=headers,
            timeout=timeout_config,
        )
        return self._handle_response(cm, stream)

    async def tag(self, name: str, repo: str, *, tag: str | None = None) -> bool:
        """
        Tag the given image so that it becomes part of a repository.

        Args:
            name: name/id of the image to be tagged
            repo: the repository to tag in
            tag: the name for the new tag
        """
        params = {"repo": repo}

        if tag:
            params["tag"] = tag

        async with self.docker._query(
            f"images/{name}/tag",
            "POST",
            params=params,
            headers={"content-type": "application/json"},
        ):
            return True

    async def delete(
        self, name: str, *, force: bool = False, noprune: bool = False
    ) -> List[Any]:
        """
        Remove an image along with any untagged parent
        images that were referenced by that image

        Args:
            name: name/id of the image to delete
            force: remove the image even if it is being used
                   by stopped containers or has other tags
            noprune: don't delete untagged parent images

        Returns:
            List of deleted images
        """
        params = {"force": force, "noprune": noprune}
        response = await self.docker._query_json(
            f"images/{name}", "DELETE", params=params
        )
        return response

    async def prune(
        self,
        *,
        filters: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Delete unused images

        Args:
            filters: Filter expressions to limit which images are pruned.
                    Available filters:
                    - dangling: When set to "true" (or "1"), prune only unused images that are not tagged.
                               When set to "false" (or "0"), prune all unused images.
                    - until: Only remove images created before given timestamp
                    - label: Only remove images with (or without, if label!=<key> is used) the specified labels

        Returns:
            Dictionary containing information about deleted images and space reclaimed
        """
        params = {}
        if filters is not None:
            params["filters"] = clean_filters(filters)

        response = await self.docker._query_json("images/prune", "POST", params=params)
        return response

    async def prune_builds(
        self,
        *,
        reserved_space: int | None = None,
        max_used_space: int | None = None,
        min_free_space: int | None = None,
        all_builds: bool | None = None,
        filters: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Delete builder cache

        Args:
            reserved_space: Amount of disk space in bytes to keep for cache.
            max_used_space: Maximum amount of disk space allowed to keep for cache.
            min_free_space: Target amount of free disk space after pruning.
            all_builds: When true, consider all unused build cache objects for pruning.
                When false, only consider dangling build cache objects for pruning.
            filters: Filter expressions to limit what types of build cache objects are pruned.
                    Available filters:
                    - until: Only remove build cache objects created before given timestamp.
                    - id: id=<id>
                    - parent: parent=<id>
                    - type: type=<string>
                    - description: description=<string>
                    - inuse
                    - shared
                    - private

        Returns:
            Dictionary containing information about deleted caches and space reclaimed
        """
        params: dict[str, Any] = {}
        if reserved_space is not None:
            params["reserved-space"] = reserved_space
        if max_used_space is not None:
            params["max-used-space"] = max_used_space
        if min_free_space is not None:
            params["min-free-space"] = min_free_space
        if all_builds is not None:
            params["all"] = all_builds
        if filters is not None:
            params["filters"] = clean_filters(filters)

        response = await self.docker._query_json("build/prune", "POST", params=params)
        return response

    @staticmethod
    async def _stream(fileobj: SupportsRead[bytes]) -> AsyncIterator[bytes]:
        chunk = fileobj.read(io.DEFAULT_BUFFER_SIZE)
        while chunk:
            yield chunk
            chunk = fileobj.read(io.DEFAULT_BUFFER_SIZE)

    @overload
    async def build(
        self,
        *,
        remote: str | None = None,
        fileobj: SupportsRead[bytes] | None = None,
        path_dockerfile: str | None = None,
        tag: str | None = None,
        quiet: bool = False,
        nocache: bool = False,
        buildargs: Mapping[str, str] | None = None,
        pull: bool = False,
        rm: bool = True,
        forcerm: bool = False,
        labels: Mapping[str, str] | None = None,
        platform: str | None = None,
        stream: Literal[False] = False,
        encoding: str | None = None,
        timeout: float | aiohttp.ClientTimeout | Sentinel | None = SENTINEL,
    ) -> List[dict[str, Any]]:
        pass

    @overload
    def build(
        self,
        *,
        remote: str | None = None,
        fileobj: SupportsRead[bytes] | None = None,
        path_dockerfile: str | None = None,
        tag: str | None = None,
        quiet: bool = False,
        nocache: bool = False,
        buildargs: Mapping[str, str] | None = None,
        pull: bool = False,
        rm: bool = True,
        forcerm: bool = False,
        labels: Mapping[str, str] | None = None,
        platform: str | None = None,
        stream: Literal[True],
        encoding: str | None = None,
        timeout: float | aiohttp.ClientTimeout | Sentinel | None = SENTINEL,
    ) -> AsyncIterator[dict[str, Any]]:
        pass

    def build(
        self,
        *,
        remote: str | None = None,
        fileobj: SupportsRead[bytes] | None = None,
        path_dockerfile: str | None = None,
        tag: str | None = None,
        quiet: bool = False,
        nocache: bool = False,
        buildargs: Mapping[str, str] | None = None,
        pull: bool = False,
        rm: bool = True,
        forcerm: bool = False,
        labels: Mapping[str, str] | None = None,
        platform: str | None = None,
        stream: bool = False,
        encoding: str | None = None,
        timeout: float | aiohttp.ClientTimeout | Sentinel | None = SENTINEL,
    ) -> Any:
        """
        Build an image given a remote Dockerfile
        or a file object with a Dockerfile inside

        Args:
            path_dockerfile: path within the build context to the Dockerfile
            remote: a Git repository URI or HTTP/HTTPS context URI
            tag: a name and optional tag to apply to the image
            quiet: suppress verbose build output
            nocache: do not use the cache when building the image
            rm: remove intermediate containers after a successful build
            pull: downloads any updates to the FROM image in Dockerfiles
            encoding: set `Content-Encoding` for the file object your send
            forcerm: always remove intermediate containers, even upon failure
            labels: arbitrary key/value labels to set on the image
            platform: platform in the format `os[/arch[/variant]]`
            fileobj: a tar archive compressed or not
            timeout: timeout for the build operation (infinite by default)

        Raises:
            DockerStreamError: If the Docker Engine reports an error in
                the build progress stream (e.g. a failing build step).
                Subclass of ``DockerError``.
        """
        headers = {}

        params = {
            "t": tag,
            "rm": rm,
            "q": quiet,
            "pull": pull,
            "remote": remote,
            "nocache": nocache,
            "forcerm": forcerm,
            "dockerfile": path_dockerfile,
        }

        if remote is None and fileobj is None:
            raise ValueError("You need to specify either remote or fileobj")

        if fileobj and remote:
            raise ValueError("You cannot specify both fileobj and remote")

        if fileobj and not encoding:
            raise ValueError("You need to specify an encoding")

        data = None
        if fileobj:
            data = self._stream(fileobj)
            headers["content-type"] = "application/x-tar"

        if fileobj and encoding:
            headers["Content-Encoding"] = encoding

        if buildargs:
            params.update({"buildargs": json.dumps(buildargs)})

        if labels:
            params.update({"labels": json.dumps(labels)})

        if platform:
            params["platform"] = platform

        # Default to infinite timeout for build operations
        timeout_config = self.docker._resolve_long_running_timeout(timeout)

        cm = self.docker._query(
            "build",
            "POST",
            params=clean_map(params),
            headers=headers,
            data=data,
            timeout=timeout_config,
        )
        return self._handle_response(cm, stream)

    def export_image(
        self,
        name: str,
        timeout: float | aiohttp.ClientTimeout | Sentinel | None = SENTINEL,
    ):
        """
        Get a tarball of an image by name or id.

        Args:
            name: name/id of the image to be exported
            timeout: timeout for the export operation (infinite by default)

        Returns:
            Streamreader of tarball image
        """
        # Default to infinite timeout for export operations
        timeout_config = self.docker._resolve_long_running_timeout(timeout)

        return _ExportCM(
            self.docker._query(f"images/{name}/get", "GET", timeout=timeout_config)
        )

    def import_image(
        self,
        data,
        stream: bool = False,
        timeout: float | aiohttp.ClientTimeout | Sentinel | None = SENTINEL,
    ):
        """
        Import tarball of image to docker.

        Args:
            data: tarball data of image to be imported
            stream: stream the response
            timeout: timeout for the import operation (infinite by default)

        Returns:
            Tarball of the image

        Raises:
            DockerStreamError: If the Docker Engine reports an error in
                the import progress stream. Subclass of ``DockerError``.
        """
        headers = {"Content-Type": "application/x-tar"}

        # Default to infinite timeout for import operations
        timeout_config = self.docker._resolve_long_running_timeout(timeout)

        cm = self.docker._query_chunked_post(
            "images/load", "POST", data=data, headers=headers, timeout=timeout_config
        )
        return self._handle_response(cm, stream)


class _ExportCM:
    def __init__(self, cm):
        self._cm = cm

    async def __aenter__(self):
        resp = await self._cm.__aenter__()
        return resp.content

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return await self._cm.__aexit__(exc_type, exc_val, exc_tb)
