import io
import json
import warnings
from typing import (
    Any,
    AsyncIterator,
    Dict,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Union,
    overload,
)

from typing_extensions import Literal

from .jsonstream import json_stream_list, json_stream_stream
from .types import SupportsRead
from .utils import clean_map, compose_auth_header


class DockerImages:
    def __init__(self, docker):
        self.docker = docker

    async def list(self, **params) -> Mapping:
        """
        List of images
        """
        response = await self.docker._query_json("images/json", "GET", params=params)
        return response

    async def inspect(self, name: str) -> Mapping:
        """
        Return low-level information about an image

        Args:
            name: name of the image
        """
        response = await self.docker._query_json(f"images/{name}/json")
        return response

    async def get(self, name: str) -> Mapping:
        warnings.warn(
            """images.get is deprecated and will be removed in the next release,
            please use images.inspect instead.""",
            DeprecationWarning,
            stacklevel=2,
        )
        return await self.inspect(name)

    async def history(self, name: str) -> Mapping:
        response = await self.docker._query_json(f"images/{name}/history")
        return response

    @overload
    async def pull(
        self,
        from_image: str,
        *,
        auth: Optional[Union[MutableMapping, str, bytes]] = None,
        tag: Optional[str] = None,
        repo: Optional[str] = None,
        stream: Literal[False] = False,
    ) -> Dict[str, Any]:
        pass

    @overload
    def pull(
        self,
        from_image: str,
        *,
        auth: Optional[Union[MutableMapping, str, bytes]] = None,
        tag: Optional[str] = None,
        repo: Optional[str] = None,
        stream: Literal[True],
    ) -> AsyncIterator[Dict[str, Any]]:
        pass

    def pull(
        self,
        from_image: str,
        *,
        auth: Optional[Union[MutableMapping, str, bytes]] = None,
        tag: Optional[str] = None,
        repo: Optional[str] = None,
        stream: bool = False,
    ) -> Any:
        """
        Similar to `docker pull`, pull an image locally

        Args:
            fromImage: name of the image to pull
            repo: repository name given to an image when it is imported
            tag: if empty when pulling an image all tags
                 for the given image to be pulled
            auth: special {'auth': base64} pull private repo
        """
        image = from_image  # TODO: clean up
        params = {"fromImage": image}
        headers = {}
        if repo:
            params["repo"] = repo
        if tag:
            params["tag"] = tag
        if auth is not None:
            registry, has_registry_host, _ = image.partition("/")
            if not has_registry_host:
                raise ValueError(
                    "Image should have registry host "
                    "when auth information is provided"
                )
            # TODO: assert registry == repo?
            headers["X-Registry-Auth"] = compose_auth_header(auth, registry)
        cm = self.docker._query("images/create", "POST", params=params, headers=headers)
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
        auth: Optional[Union[MutableMapping, str, bytes]] = None,
        tag: Optional[str] = None,
        stream: Literal[False] = False,
    ) -> Dict[str, Any]:
        pass

    @overload
    def push(
        self,
        name: str,
        *,
        auth: Optional[Union[MutableMapping, str, bytes]] = None,
        tag: Optional[str] = None,
        stream: Literal[True],
    ) -> AsyncIterator[Dict[str, Any]]:
        pass

    def push(
        self,
        name: str,
        *,
        auth: Optional[Union[MutableMapping, str, bytes]] = None,
        tag: Optional[str] = None,
        stream: bool = False,
    ) -> Any:
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
                    "Image should have registry host "
                    "when auth information is provided"
                )
            headers["X-Registry-Auth"] = compose_auth_header(auth, registry)
        cm = self.docker._query(
            f"images/{name}/push",
            "POST",
            params=params,
            headers=headers,
        )
        return self._handle_response(cm, stream)

    async def tag(self, name: str, repo: str, *, tag: Optional[str] = None) -> bool:
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
    ) -> List:
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
        return await self.docker._query_json(f"images/{name}", "DELETE", params=params)

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
        remote: Optional[str] = None,
        fileobj: Optional[SupportsRead[bytes]] = None,
        path_dockerfile: Optional[str] = None,
        tag: Optional[str] = None,
        quiet: bool = False,
        nocache: bool = False,
        buildargs: Optional[Mapping] = None,
        pull: bool = False,
        rm: bool = True,
        forcerm: bool = False,
        labels: Optional[Mapping] = None,
        stream: Literal[False] = False,
        encoding: Optional[str] = None,
    ) -> Dict[str, Any]:
        pass

    @overload
    def build(
        self,
        *,
        remote: Optional[str] = None,
        fileobj: Optional[SupportsRead[bytes]] = None,
        path_dockerfile: Optional[str] = None,
        tag: Optional[str] = None,
        quiet: bool = False,
        nocache: bool = False,
        buildargs: Optional[Mapping] = None,
        pull: bool = False,
        rm: bool = True,
        forcerm: bool = False,
        labels: Optional[Mapping] = None,
        stream: Literal[True],
        encoding: Optional[str] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        pass

    def build(
        self,
        *,
        remote: Optional[str] = None,
        fileobj: Optional[SupportsRead[bytes]] = None,
        path_dockerfile: Optional[str] = None,
        tag: Optional[str] = None,
        quiet: bool = False,
        nocache: bool = False,
        buildargs: Optional[Mapping] = None,
        pull: bool = False,
        rm: bool = True,
        forcerm: bool = False,
        labels: Optional[Mapping] = None,
        stream: bool = False,
        encoding: Optional[str] = None,
    ) -> Any:
        """
        Build an image given a remote Dockerfile
        or a file object with a Dockerfile inside

        Args:
            path_dockerfile: path within the build context to the Dockerfile
            remote: a Git repository URI or HTTP/HTTPS context URI
            quiet: suppress verbose build output
            nocache: do not use the cache when building the image
            rm: remove intermediate containers after a successful build
            pull: downloads any updates to the FROM image in Dockerfiles
            encoding: set `Content-Encoding` for the file object your send
            forcerm: always remove intermediate containers, even upon failure
            labels: arbitrary key/value labels to set on the image
            fileobj: a tar archive compressed or not
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

        cm = self.docker._query(
            "build",
            "POST",
            params=clean_map(params),
            headers=headers,
            data=data,
        )
        return self._handle_response(cm, stream)

    def export_image(self, name: str):
        """
        Get a tarball of an image by name or id.

        Args:
            name: name/id of the image to be exported

        Returns:
            Streamreader of tarball image
        """
        return _ExportCM(self.docker._query(f"images/{name}/get", "GET"))

    def import_image(self, data, stream: bool = False):
        """
        Import tarball of image to docker.

        Args:
            data: tarball data of image to be imported

        Returns:
            Tarball of the image
        """
        headers = {"Content-Type": "application/x-tar"}
        cm = self.docker._query_chunked_post(
            "images/load", "POST", data=data, headers=headers
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
