import re

from .resource import Model, Collection
from ..errors import BuildError
from ..utils.utils import parse_repository_tag, clean_map


class Image(Model):
    """
    An image on the server.
    """
    def __repr__(self):
        return "<{}: '{}'>".format(self.__class__.__name__, "', '".join(self.tags))

    @property
    def labels(self):
        """
        The labels of an image as dictionary.
        """
        result = self.attrs['Config'].get('Labels')
        return result or {}

    @property
    def short_id(self):
        """
        The ID of the image truncated to 10 characters, plus the ``sha256:``
        prefix.
        """
        if self.id.startswith('sha256:'):
            return self.id[:17]
        return self.id[:10]

    @property
    def tags(self):
        """
        The image's tags.
        """
        tags = self.attrs.get('RepoTags')
        if tags is None:
            tags = []
        return [tag for tag in tags if tag != '<none>:<none>']

    async def history(self):
        """
        Show the history of an image.

        Returns:
            (str): The history of the image.

        Raises:
            :py:class:`aiodocker.errors.APIError`
                If the server returns an error.
        """
        return await self.client.api.image.history(self.id)

    # def save(self, chunk_size=DEFAULT_DATA_CHUNK_SIZE):
    #     """
    #     Get a tarball of an image. Similar to the ``docker save`` command.
    #
    #     Args:
    #         chunk_size (int): The number of bytes returned by each iteration
    #             of the generator. If ``None``, data will be streamed as it is
    #             received. Default: 2 MB
    #
    #     Returns:
    #         (generator): A stream of raw archive data.
    #
    #     Raises:
    #         :py:class:`docker.errors.APIError`
    #             If the server returns an error.
    #
    #     Example:
    #
    #         >>> image = cli.get_image("busybox:latest")
    #         >>> f = open('/tmp/busybox-latest.tar', 'w')
    #         >>> for chunk in image:
    #         >>>   f.write(chunk)
    #         >>> f.close()
    #     """
    #     return self.client.api.get_image(self.id, chunk_size)

    def tag(self, repository, tag=None):
        """
        Tag this image into a repository. Similar to the ``docker tag``
        command.

        Args:
            repository (str): The repository to set for the tag
            tag (str): The tag name

        Raises:
            :py:class:`aiodocker.errors.APIError`
                If the server returns an error.

        Returns:
            (bool): ``True`` if successful
        """
        return self.client.api.image.tag(self.id, repository, tag=tag)


class ImageCollection(Collection):
    model = Image

    async def build(self, **kwargs):
        """
        Build an image and return it. Similar to the ``docker build``
        command. Either ``path`` or ``fileobj`` must be set.

        If you have a tar file for the Docker build context (including a
        Dockerfile) already, pass a readable file-like object to ``fileobj``
        and also pass ``custom_context=True``. If the stream is compressed
        also, set ``encoding`` to the correct value (e.g ``gzip``).

        If you want to get the raw output of the build, use the
        :py:meth:`~docker.api.build.BuildApiMixin.build` method in the
        low-level API.

        Args:
            path (str): Path to the directory containing the Dockerfile
            fileobj: A file object to use as the Dockerfile. (Or a file-like
                object)
            tag (str): A tag to add to the final image
            quiet (bool): Whether to return the status
            nocache (bool): Don't use the cache when set to ``True``
            rm (bool): Remove intermediate containers. The ``docker build``
                command now defaults to ``--rm=true``, but we have kept the old
                default of `False` to preserve backward compatibility
            timeout (int): HTTP timeout
            custom_context (bool): Optional if using ``fileobj``
            encoding (str): The encoding for a stream. Set to ``gzip`` for
                compressing
            pull (bool): Downloads any updates to the FROM image in Dockerfiles
            forcerm (bool): Always remove intermediate containers, even after
                unsuccessful builds
            dockerfile (str): path within the build context to the Dockerfile
            buildargs (dict): A dictionary of build arguments
            container_limits (dict): A dictionary of limits applied to each
                container created by the build process. Valid keys:

                - memory (int): set memory limit for build
                - memswap (int): Total memory (memory + swap), -1 to disable
                    swap
                - cpushares (int): CPU shares (relative weight)
                - cpusetcpus (str): CPUs in which to allow execution, e.g.,
                    ``"0-3"``, ``"0,1"``
            shmsize (int): Size of `/dev/shm` in bytes. The size must be
                greater than 0. If omitted the system uses 64MB
            labels (dict): A dictionary of labels to set on the image
            cache_from (list): A list of images used for build cache
                resolution
            target (str): Name of the build-stage to build in a multi-stage
                Dockerfile
            network_mode (str): networking mode for the run commands during
                build
            squash (bool): Squash the resulting images layers into a
                single layer.
            extra_hosts (dict): Extra hosts to add to /etc/hosts in building
                containers, as a mapping of hostname to IP address.
            platform (str): Platform in the format ``os[/arch[/variant]]``.

        Returns:
            (tuple): The first item is the :py:class:`Image` object for the
                image that was build. The second item is a generator of the
                build logs as JSON-decoded objects.

        Raises:
            :py:class:`docker.errors.BuildError`
                If there is an error during the build.
            :py:class:`docker.errors.APIError`
                If the server returns any other error.
            ``TypeError``
                If neither ``path`` nor ``fileobj`` is specified.
        """
        json_stream = await self.client.api.image.build(**kwargs)
        if isinstance(json_stream, str):
            return self.get(json_stream)
        last_event = None
        image_id = None
        for chunk in json_stream:
            if 'error' in chunk:
                raise BuildError(chunk['error'], json_stream)
            if 'stream' in chunk:
                match = re.search(
                    r'(^Successfully built |sha256:)([0-9a-f]+)$',
                    chunk['stream']
                )
                if match:
                    image_id = match.group(2)
            last_event = chunk
        if image_id:
            return await self.get(image_id), json_stream
        raise BuildError(last_event or 'Unknown', json_stream)

    async def get(self, name):
        """
        Gets an image.

        Args:
            name (str): The name of the image.

        Returns:
            (:py:class:`Image`): The image.

        Raises:
            :py:class:`aiodocker.errors.ImageNotFound`
                If the image does not exist.
            :py:class:`aiodocker.errors.APIError`
                If the server returns an error.
        """
        return self.prepare_model(await self.client.api.image.inspect(name))

    async def list(self, name=None, all=False, digests=False, filters=None):
        """
        List images on the server.

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
            (list of :py:class:`Image`): The images.

        Raises:
            :py:class:`aiodocker.errors.APIError`
                If the server returns an error.
        """
        resp = await self.client.api.image.list(name=name, all=all, digests=digests, filters=filters)
        return [await self.get(r["Id"]) for r in resp]

    async def create(self, attrs=None):
        pass

    async def pull(self, repository, tag=None, **kwargs):
        """
        Pull an image of the given name and return it. Similar to the
        ``docker pull`` command.
        If no tag is specified, all tags from that repository will be
        pulled.

        If you want to get the raw pull output, use the
        :py:meth:`~aiodocker.api.image.pull` method in the
        low-level API.

        Args:
            repository (str): The repository to pull
            tag (str): The tag to pull
            auth_config (dict): Override the credentials that
                :py:meth:`~aiodocker.client.DockerClient.login` has set for
                this request. ``auth_config`` should contain the ``username``
                and ``password`` keys to be valid.

        Returns:
            (:py:class:`Image` or list): The image that has been pulled.
                If no ``tag`` was specified, the method will return a list
                of :py:class:`Image` objects belonging to this repository.

        Raises:
            :py:class:`aiodocker.errors.APIError`
                If the server returns an error.

        Example:

        .. code-block:: python

            >>> # Pull the image tagged `latest` in the busybox repo
            >>> image = client.images.pull('busybox:latest')

            >>> # Pull all tags in the busybox repo
            >>> images = client.images.pull('busybox')
        """
        if not tag:
            repository, tag = parse_repository_tag(repository)

        await self.client.api.image.pull(repository, tag=tag, **kwargs)
        if tag:
            return await self.get('{0}{2}{1}'.format(
                repository, tag, '@' if tag.startswith('sha256:') else ':'
            ))
        return await self.list(repository)

    async def push(self, repository, tag=None, **kwargs):
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
            >>> for line in client.images.push('yourname/app', stream=True):
            ...   print line
            {"status":"Pushing repository yourname/app (1 tags)"}
            {"status":"Pushing","progressDetail":{},"id":"511136ea3c5a"}
            {"status":"Image already pushed, skipping","progressDetail":{},
             "id":"511136ea3c5a"}
            ...

        """
        return await self.client.api.image.push(repository, tag=tag, **kwargs)

    async def remove(self, name: str, force: bool = False, noprune: bool = False):
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
        return await self.client.api.image.remove(name, force=force, noprune=noprune)


