import io
import json
import warnings
from typing import (
    AsyncIterator,
    BinaryIO,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Union,
)

from .jsonstream import json_stream_list, json_stream_stream
from .utils import clean_map, compose_auth_header


class DockerImages(object):
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
        response = await self.docker._query_json("images/{name}/json".format(name=name))
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
        response = await self.docker._query_json(
            "images/{name}/history".format(name=name)
        )
        return response

    def pull(
        self,
        from_image: str,
        *,
        auth: Optional[Union[MutableMapping, str, bytes]] = None,
        tag: str = None,
        repo: str = None,
        stream: bool = False,
    ) -> Mapping:
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

    def push(
        self,
        name: str,
        *,
        auth: Union[MutableMapping, str, bytes] = None,
        tag: str = None,
        stream: bool = False,
    ) -> Mapping:
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
            "images/{name}/push".format(name=name),
            "POST",
            params=params,
            headers=headers,
        )
        return self._handle_response(cm, stream)

    async def tag(self, name: str, repo: str, *, tag: str = None) -> bool:
        """
        Tag the given image so that it becomes part of a repository.

        Args:
            repo: the repository to tag in
            tag: the name for the new tag
        """
        params = {"repo": repo}

        if tag:
            params["tag"] = tag

        async with self.docker._query(
            "images/{name}/tag".format(name=name),
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
        return await self.docker._query_json(
            "images/{name}".format(name=name), "DELETE", params=params
        )

    @staticmethod
    async def _stream(fileobj: BinaryIO) -> AsyncIterator[bytes]:
        chunk = fileobj.read(io.DEFAULT_BUFFER_SIZE)
        while chunk:
            yield chunk
            chunk = fileobj.read(io.DEFAULT_BUFFER_SIZE)

    def build(
        self,
        *,
        remote: str = None,
        fileobj: BinaryIO = None,
        path_dockerfile: str = None,
        tag: str = None,
        quiet: bool = False,
        nocache: bool = False,
        buildargs: Mapping = None,
        pull: bool = False,
        rm: bool = True,
        forcerm: bool = False,
        labels: Mapping = None,
        stream: bool = False,
        encoding: str = None,
    ) -> Mapping:
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

        if remote is None and fileobj is None:
            raise ValueError("Either remote or fileobj needs to be provided.")

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
            "build", "POST", params=clean_map(params), headers=headers, data=data,
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
        return _ExportCM(
            self.docker._query("images/{name}/get".format(name=name), "GET")
        )

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
