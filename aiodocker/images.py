import json
import base64
from typing import Optional, Union, List, Dict, BinaryIO
from .utils import clean_config, parse_base64_auth
from .jsonstream import json_stream_result


class DockerImages(object):
    def __init__(self, docker):
        self.docker = docker

    async def list(self, **params) -> Dict:
        """
        List of images
        """
        response = await self.docker._query_json(
            "images/json", "GET",
            params=params,
            headers={"content-type": "application/json", },
        )
        return response

    async def get(self, name: str) -> Dict:
        """
        Return low-level information about an image

        Args:
            name: name of the image
        """
        response = await self.docker._query_json(
            "images/{name}/json".format(name=name),
            headers={"content-type": "application/json", },
        )
        return response

    async def history(self, name: str) -> Dict:
        response = await self.docker._query_json(
            "images/{name}/history".format(name=name),
            headers={"content-type": "application/json", },
        )
        return response

    async def pull(self, from_image: str, *, repo: Optional[str]=None,
                   tag: Optional[str]=None, auth: Optional[dict]=None,
                   stream: bool=False) -> Dict:
        """
        Similar to `docker pull`, pull an image locally

        Args:
            fromImage: name of the image to pull
            repo: repository name given to an image when it is imported
            tag: if empty when pulling an image all tags
                 for the given image to be pulled
            auth: special {'auth': base64} pull private repo
        """

        params = {}

        if from_image:
            params['fromImage'] = from_image

        if repo:
            params['repo'] = repo

        if tag:
            params['tag'] = tag

        headers = {"content-type": "application/json"}

        if auth and 'auth' in auth:
            auth_header = parse_base64_auth(auth['auth'], repo)
            headers.update({"X-Registry-Auth": auth_header})

        response = await self.docker._query(
            "images/create",
            "POST",
            params=params,
            headers=headers,
        )
        return (await json_stream_result(response, stream=stream))

    async def push(self, name: str, *, tag: Optional[str]=None,
                   auth: Union[Dict, str, bytes]=None,
                   stream: bool=False) -> Dict:
        headers = {
            "content-type": "application/json",
            "X-Registry-Auth": "FOO",
        }
        params = {}
        if auth:
            if isinstance(auth, dict):
                auth = json.dumps(auth).encode('ascii')
                auth = base64.b64encode(auth)
            if not isinstance(auth, (bytes, str)):
                raise TypeError(
                    "auth must be base64 encoded string/bytes or a dictionary")
            if isinstance(auth, bytes):
                auth = auth.decode('ascii')
            headers['X-Registry-Auth'] = auth
        if tag:
            params['tag'] = tag
        response = await self.docker._query(
            "images/{name}/push".format(name=name),
            "POST",
            params=params,
            headers=headers,
        )
        return (await json_stream_result(response, stream=stream))

    async def tag(self, name: str, repo: str, *,
                  tag: Optional[str]=None) -> bool:
        """
        Tag the given image so that it becomes part of a repository.

        Args:
            repo: the repository to tag in
            tag: the name for the new tag
        """
        params = {"repo": repo}

        if tag:
            params["tag"] = tag

        await self.docker._query(
            "images/{name}/tag".format(name=name),
            "POST",
            params=params,
            headers={"content-type": "application/json"},
        )
        return True

    async def delete(self, name: str, *, force: bool=False,
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
        response = await self.docker._query_json(
            "images/{name}".format(name=name),
            "DELETE",
            params=params,
        )
        return response

    async def build(self, *,
                    remote: Optional[str]=None,
                    fileobj: Optional[BinaryIO]=None,
                    path_dockerfile: Optional[str]=None,
                    tag: Optional[str]=None,
                    quiet: bool=False,
                    nocache: bool=False,
                    buildargs: Optional[Dict]=None,
                    pull: bool=False,
                    rm: bool=True,
                    forcerm: bool=False,
                    labels: Optional[Dict]=None,
                    stream: bool=False,
                    encoding: Optional[str]=None) -> Dict:
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

        response = await self.docker._query(
            "build",
            "POST",
            params=clean_config(params),
            headers=headers,
            data=local_context
        )

        return (await json_stream_result(response, stream=stream))
