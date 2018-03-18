import json
import tarfile
from typing import (
    Optional, Union, Any,
    List, MutableMapping, Mapping,
    BinaryIO,
)

from ..jsonstream import json_stream_result
from ..multiplexed import multiplexed_result
from ..utils import identical, parse_result, clean_filters, compose_auth_header, clean_map


class DockerImageAPI(object):
    def __init__(self, api_client):
        self.api_client = api_client

    async def build(self, *,
                    remote: str=None,
                    fileobj: BinaryIO=None,
                    path_dockerfile: str=None,
                    tag: str=None,
                    quiet: bool=False,
                    nocache: bool=False,
                    buildargs: Mapping=None,
                    pull: bool=False,
                    rm: bool=True,
                    forcerm: bool=False,
                    labels: Mapping=None,
                    stream: bool=False,
                    encoding: str=None) -> Mapping:
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
            tag (str): A tag to add to the final image
            buildargs (dict): A dictionary of build arguments
            stream:
        """

        local_context = None

        headers = {}

        params = {
            't': tag,
            'rm': rm,
            'q': quiet,
            'pull': pull,
            'remote': remote,
            'nocache': nocache,
            'forcerm': forcerm,
            'dockerfile': path_dockerfile,
        }

        if remote is None and fileobj is None:
            raise ValueError("You need to specify either remote or fileobj")

        if fileobj and remote:
            raise ValueError("You cannot specify both fileobj and remote")

        if fileobj and not encoding:
            raise ValueError("You need to specify an encoding")

        if remote is None and fileobj is None:
            raise ValueError("Either remote or fileobj needs to be provided.")

        if fileobj:
            local_context = fileobj.read()
            headers["content-type"] = "application/x-tar"

        if fileobj and encoding:
            headers['Content-Encoding'] = encoding

        if buildargs:
            params.update({'buildargs': json.dumps(buildargs)})

        if labels:
            params.update({'labels': json.dumps(labels)})

        response = await self.api_client._query(
            "build",
            "POST",
            params=clean_map(params),
            headers=headers,
            data=local_context
        )

        return await json_stream_result(response, stream=stream)

    async def history(self, image: str) -> Mapping:
        """
        Show the history of an image.

        Args:
            image (str): The image to show history for

        Returns:
            (str): The history of the image

        Raises:
            :py:class:`aiodocker.errors.APIError`
                If the server returns an error.
        """
        response = await self.api_client._query_json(
            "images/{name}/history".format(name=image),
        )
        return response

    async def inspect(self, image: str) -> Mapping[str, Any]:
        """
        Get detailed information about an image. Similar to the ``docker
        image inspect`` command.

        Args:
            image (str): The image to inspect

        Returns:
            (dict): Similar to the output of ``docker image inspect``, but as a
        single dict

        Raises:
            :py:class:`aiodocker.errors.APIError`
                If the server returns an error.
        """
        response = await self.api_client._query_json(
            "images/{image}/json".format(image=image),
        )
        return response

    async def list(self, name=None, all=False, digests=False, filters: Mapping=None) -> List[Mapping]:
        """
        List images. Similar to the ``docker images`` command.

        Args:
            name (str): Only show images belonging to the repository ``name``
            all (bool): Show intermediate image layers. By default, these are
                filtered out.
            digests (bool): Show digest information as a RepoDigests field on each image.
            filters (dict): Filters to be processed on the image list.
                Available filters:
                - ``dangling`` (bool)
                - ``label`` (str): format either ``key`` or ``key=value``
                - before=(<image-name>[:<tag>], <image id> or <image@digest>)
                - reference=(<image-name>[:<tag>])
                - since=(<image-name>[:<tag>], <image id> or <image@digest>)

        Returns:
            A dictionary.

        Raises:
            :py:class:`aiodocker.errors.APIError`
                If the server returns an error.
        """
        params = {
            'all': all,
            'digests': digests
        }
        if name:
            params['filter'] = name
        if filters:
            params['filters'] = clean_filters(filters)
        response = await self.api_client._query_json(
            "images/json", "GET",
            params=params,
        )
        return response

    async def pull(self, name: str, *,
                   auth_config: Optional[Union[MutableMapping, str, bytes]]=None,
                   tag: str=None,
                   repo: str=None,
                   stream: bool=False,
                   platform=None) -> Mapping:
        """
        Similar to `docker pull`, pull an image locally

        Args:
            name: name of the image to pull
            repo: repository name given to an image when it is imported
            tag: if empty when pulling an image all tags
                 for the given image to be pulled
            auth_config: special {'auth': base64} pull private repo
            stream:
            platform (str): Platform in the format ``os[/arch[/variant]]``
        """
        params = {
            'fromImage': name,
        }
        headers = {}
        if repo:
            params['repo'] = repo
        if tag:
            params['tag'] = tag
        if auth_config is not None:
            registry, has_registry_host, _ = name.partition('/')
            if not has_registry_host:
                raise ValueError('Image should have registry host '
                                 'when auth information is provided')
            # TODO: assert registry == repo?
            headers['X-Registry-Auth'] = compose_auth_header(auth_config, registry)
        response = await self.api_client._query(
            "images/create",
            "POST",
            params=clean_map(params),
            headers=headers,
        )
        return await json_stream_result(response, stream=stream)

    async def push(self, repository: str, *,
                   auth_config: Union[MutableMapping, str, bytes]=None,
                   tag: str=None,
                   stream: bool=False) -> Mapping:
        """
        Push an image or a repository to the registry. Similar to the ``docker
        push`` command.

        Args:
            repository (str): The repository to push to
            tag (str): An optional tag to push
            stream (bool): Stream the output as a blocking generator
            auth_config (dict): Override the credentials that
                :py:meth:`~docker.api.daemon.DaemonApiMixin.login` has set for
                this request. ``auth_config`` should contain the ``username``
                and ``password`` keys to be valid.
            decode (bool): Decode the JSON data from the server into dicts.
                Only applies with ``stream=True``

        Returns:
            (generator or str): The output from the server.

        Raises:
            :py:class:`aiodocker.errors.APIError`
                If the server returns an error.

        Example:
            >>> for line in client.image.push('yourname/app', stream=True):
            ...   print line
            {"status":"Pushing repository yourname/app (1 tags)"}
            {"status":"Pushing","progressDetail":{},"id":"511136ea3c5a"}
            {"status":"Image already pushed, skipping","progressDetail":{},
             "id":"511136ea3c5a"}
            ...

        """
        params = {}
        headers = {
            # Anonymous push requires a dummy auth header.
            'X-Registry-Auth': 'placeholder',
        }
        if tag:
            params['tag'] = tag
        if auth_config is not None:
            registry, has_registry_host, _ = repository.partition('/')
            if not has_registry_host:
                raise ValueError('Image should have registry host '
                                 'when auth information is provided')
            headers['X-Registry-Auth'] = compose_auth_header(auth_config, registry)
        response = await self.api_client._query(
            "images/{name}/push".format(name=repository),
            "POST",
            params=params,
            headers=headers,
        )
        return await json_stream_result(response, stream=stream)

    async def remove(self, name: str, *, force: bool=False,
                     noprune: bool=False) -> List:
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
        params = {'force': force, 'noprune': noprune}
        response = await self.api_client._query_json(
            "images/{name}".format(name=name),
            "DELETE",
            params=params,
        )
        return response

    async def tag(self, image: str, repository: str, *, tag: str=None) -> bool:
        """
        Tag an image into a repository. Similar to the ``docker tag`` command.

        Args:
            image (str): The image to tag
            repository (str): The repository to set for the tag
            tag (str): The tag name

        Returns:
            (bool): ``True`` if successful

        Raises:
            :py:class:`aiodocker.errors.APIError`
                If the server returns an error.

        Example:

            >>> client.image.tag('ubuntu', 'localhost:5000/ubuntu', 'latest')
        """
        params = {"repo": repository}

        if tag:
            params["tag"] = tag

        await self.api_client._query_json(
            "images/{image}/tag".format(image=image),
            "POST",
            params=params,
        )
        return True
