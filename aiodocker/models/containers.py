import copy
import ntpath

from .resource import Collection, Model
from ..errors import ImageNotFound, ContainerError, APIError, create_unexpected_kwargs_error
from ..exceptions import DockerContainerError
from ..types import HostConfig
from .images import Image


class Container(Model):

    @property
    def name(self):
        """
        The name of the container.
        """
        if self.attrs.get('Name') is not None:
            return self.attrs['Name'].lstrip('/')

    @property
    def labels(self):
        """
        The labels of a container as dictionary.
        """
        result = self.attrs['Config'].get('Labels')
        return result or {}

    @property
    def status(self):
        """
        The status of the container. For example, ``running``, or ``exited``.
        """
        return self.attrs['State']['Status']

    async def image(self):
        """
        The image of the container.
        """
        image_id = self.attrs['Image']
        if image_id is None:
            return None
        return await self.client.api.image.get(image_id.split(':')[1])

    async def logs(self, **kwargs):
        """
        Get logs from this container. Similar to the ``docker logs`` command.

        The ``stream`` parameter makes the ``logs`` function return a blocking
        generator you can iterate over to retrieve log output as it happens.

        Args:
            stdout (bool): Get ``STDOUT``
            stderr (bool): Get ``STDERR``
            stream (bool): Stream the response
            timestamps (bool): Show timestamps
            tail (str or int): Output specified number of lines at the end of
                logs. Either an integer of number of lines or the string
                ``all``. Default ``all``
            since (datetime or int): Show logs since a given datetime or
                integer epoch (in seconds)
            follow (bool): Follow log output
            until (datetime or int): Show logs that occurred before the given
                datetime or integer epoch (in seconds)

        Returns:
            (generator or str): Logs from the container.

        Raises:
            :py:class:`aiodocker.errors.APIError`
                If the server returns an error.
        """
        return await self.client.api.container.logs(self.id, **kwargs)

    async def remove(self, v=False, link=False, force=False):
        """
        Remove this container. Similar to the ``docker rm`` command.

        Args:
            v (bool): Remove the volumes associated with the container
            link (bool): Remove the specified link and not the underlying
                container
            force (bool): Force the removal of a running container (uses
                ``SIGKILL``)

        Raises:
            :py:class:`aiodocker.errors.APIError`
                If the server returns an error.
        """
        return await self.client.api.container.remove(self.id, v=v, link=link, force=force)

    async def restart(self, timeout=None):
        """
        Restart this container. Similar to the ``docker restart`` command.

        Args:
            timeout (int): Number of seconds to try to stop for before killing
                the container. Once killed it will then be restarted. Default
                is 10 seconds.

        Raises:
            :py:class:`aiodocker.errors.APIError`
                If the server returns an error.
        """
        return await self.client.api.container.restart(self.id, timeout)

    async def start(self, **kwargs):
        """
        Start this container. Similar to the ``docker start`` command, but
        doesn't support attach options.

        Raises:
            :py:class:`aiodocker.errors.APIError`
                If the server returns an error.
        """
        return await self.client.api.container.start(self.id, **kwargs)

    def stop(self, **kwargs):
        """
        Stops a container. Similar to the ``docker stop`` command.

        Args:
            timeout (int): Timeout in seconds to wait for the container to
                stop before sending a ``SIGKILL``. Default: 10

        Raises:
            :py:class:`aiodocker.errors.APIError`
                If the server returns an error.
        """
        return self.client.api.container.stop(self.id, **kwargs)

    async def wait(self, **kwargs):
        """
        Block until the container stops, then return its exit code. Similar to
        the ``docker wait`` command.

        Args:
            timeout (int): Request timeout
            condition (str): Wait until a container state reaches the given
                condition, either ``not-running`` (default), ``next-exit``,
                or ``removed``

        Returns:
            (dict): The API's response as a Python dictionary, including
                the container's exit code under the ``StatusCode`` attribute.

        Raises:
            :py:class:`aiohttp.ServerTimeoutError`
                If the timeout is exceeded.
            :py:class:`aiodocker.errors.APIError`
                If the server returns an error.
        """
        return await self.client.api.container.wait(self.id, **kwargs)


class ContainerCollection(Collection):
    model = Container

    async def get(self, container_id):
        """
        Get a container by name or ID.

        Args:
            container_id (str): Container name or ID.

        Returns:
            A :py:class:`Container` object.

        Raises:
            :py:class:`aiodocker.errors.NotFound`
                If the container does not exist.
            :py:class:`aiodocker.errors.APIError`
                If the server returns an error.
        """
        resp = await self.client.api.container.inspect(container_id)
        return self.prepare_model(resp)

    async def create(self, image, command=None, **kwargs):
        """
        Create a container without starting it. Similar to ``docker create``.

        Takes the same arguments as :py:meth:`run`, except for ``stdout``,
        ``stderr``, and ``remove``.

        Returns:
            A :py:class:`Container` object.

        Raises:
            :py:class:`aiodocker.errors.ImageNotFound`
                If the specified image does not exist.
            :py:class:`aiodocker.errors.APIError`
                If the server returns an error.
        """
        if isinstance(image, Image):
            image = image.id
        kwargs['image'] = image
        kwargs['command'] = command
        kwargs['version'] = self.client.api.api_version
        create_kwargs = _create_container_args(kwargs)
        resp = await self.client.api.container.create(**create_kwargs)
        return await self.get(resp['Id'])

    async def list(self, all=False, limit=-1, filters=None):
        """
        List containers. Similar to the ``docker ps`` command.

        Args:
            all (bool): Show all containers. Only running containers are shown
                by default
            limit (int): Show `limit` last created containers, include
                non-running ones
            filters (dict): Filters to be processed on the image list.
                Available filters:

                - `exited` (int): Only containers with specified exit code
                - `status` (str): One of ``restarting``, ``running``,
                    ``paused``, ``exited``
                - `label` (str): format either ``"key"`` or ``"key=value"``
                - `id` (str): The id of the container.
                - `name` (str): The name of the container.
                - `ancestor` (str): Filter by container ancestor. Format of
                    ``<image-name>[:tag]``, ``<image-id>``, or
                    ``<image@digest>``.
                - `before` (str): Only containers created before a particular
                    container. Give the container name or id.
                - `since` (str): Only containers created after a particular
                    container. Give container name or id.

                A comprehensive list can be found in the documentation for
                `docker ps
                <https://docs.docker.com/engine/reference/commandline/ps>`_.

        Returns:
            (list of :py:class:`Container`)

        Raises:
            :py:class:`aiodocker.errors.APIError`
                If the server returns an error.
        """
        resp = await self.client.api.container.list(all=all, limit=limit, filters=filters)
        return [await self.get(r['Id']) for r in resp]

    async def run(self, image, command=None, stdout=True, stderr=False,
                  remove=False, **kwargs):
        """
        Create and start a container.

        If container.start() will raise an error the exception will contain
        a `container_id` attribute with the id of the container.
        """
        if isinstance(image, Image):
            image = image.id
        stream = kwargs.pop('stream', False)
        detach = kwargs.pop('detach', False)
        platform = kwargs.pop('platform', None)

        if detach and remove:
            kwargs["auto_remove"] = True

        if kwargs.get('network') and kwargs.get('network_mode'):
            raise RuntimeError(
                'The options "network" and "network_mode" can not be used '
                'together.'
            )

        try:
            container = await self.create(image=image, command=command,
                                          detach=detach, **kwargs)
        except ImageNotFound:
            await self.client.images.pull(image, platform=platform)
            container = await self.create(image=image, command=command,
                                          detach=detach, **kwargs)

        try:
            await container.start()
        except APIError as err:
            raise DockerContainerError(
                err.status_code,
                {
                    "message": err.explanation
                },
                container.id
            )

        return container

    async def prune(self, filters=None):
        """
        Delete stopped containers

        Args:
            filters (dict): Filters to process on the prune list.

        Returns:
            (dict): A dict containing a list of deleted container IDs and
                the amount of disk space reclaimed in bytes.

        Raises:
            :py:class:`aiodocker.errors.APIError`
                If the server returns an error.
        """
        return await self.client.api.container.prune(filters=filters)


# kwargs to copy straight from run to create
RUN_CREATE_KWARGS = [
    'command',
    'detach',
    'domainname',
    'entrypoint',
    'environment',
    'healthcheck',
    'hostname',
    'image',
    'labels',
    'mac_address',
    'name',
    'network_disabled',
    'stdin_open',
    'stop_signal',
    'tty',
    'user',
    'volume_driver',
    'working_dir',
]

# kwargs to copy straight from run to host_config
RUN_HOST_CONFIG_KWARGS = [
    'auto_remove',
    'blkio_weight_device',
    'blkio_weight',
    'cap_add',
    'cap_drop',
    'cgroup_parent',
    'cpu_count',
    'cpu_percent',
    'cpu_period',
    'cpu_quota',
    'cpu_shares',
    'cpuset_cpus',
    'cpuset_mems',
    'cpu_rt_period',
    'cpu_rt_runtime',
    'device_cgroup_rules',
    'device_read_bps',
    'device_read_iops',
    'device_write_bps',
    'device_write_iops',
    'devices',
    'dns_opt',
    'dns_search',
    'dns',
    'extra_hosts',
    'group_add',
    'init',
    'init_path',
    'ipc_mode',
    'isolation',
    'kernel_memory',
    'links',
    'log_config',
    'lxc_conf',
    'mem_limit',
    'mem_reservation',
    'mem_swappiness',
    'memswap_limit',
    'mounts',
    'nano_cpus',
    'network_mode',
    'oom_kill_disable',
    'oom_score_adj',
    'pid_mode',
    'pids_limit',
    'privileged',
    'publish_all_ports',
    'read_only',
    'restart_policy',
    'security_opt',
    'shm_size',
    'storage_opt',
    'sysctls',
    'tmpfs',
    'ulimits',
    'userns_mode',
    'version',
    'volumes_from',
    'runtime'
]


def _create_container_args(kwargs):
    """
    Convert arguments to create() to arguments to create_container().
    """
    # Copy over kwargs which can be copied directly
    create_kwargs = {}
    for key in copy.copy(kwargs):
        if key in RUN_CREATE_KWARGS:
            create_kwargs[key] = kwargs.pop(key)
    host_config_kwargs = {}
    for key in copy.copy(kwargs):
        if key in RUN_HOST_CONFIG_KWARGS:
            host_config_kwargs[key] = kwargs.pop(key)

    # Process kwargs which are split over both create and host_config
    ports = kwargs.pop('ports', {})
    if ports:
        host_config_kwargs['port_bindings'] = ports

    volumes = kwargs.pop('volumes', {})
    if volumes:
        host_config_kwargs['binds'] = volumes

    network = kwargs.pop('network', None)
    if network:
        create_kwargs['networking_config'] = {
            network: None
        }
        host_config_kwargs['network_mode'] = network

    # All kwargs should have been consumed by this point, so raise
    # error if any are left
    if kwargs:
        raise create_unexpected_kwargs_error('run', kwargs)

    create_kwargs['host_config'] = HostConfig(**host_config_kwargs)

    # Fill in any kwargs which need processing by create_host_config first
    port_bindings = create_kwargs['host_config'].get('PortBindings')
    if port_bindings:
        # sort to make consistent for tests
        create_kwargs['ports'] = [tuple(p.split('/', 1))
                                  for p in sorted(port_bindings.keys())]
    if volumes:
        if isinstance(volumes, dict):
            create_kwargs['volumes'] = [
                v.get('bind') for v in volumes.values()
            ]
        else:
            create_kwargs['volumes'] = [
                _host_volume_from_bind(v) for v in volumes
            ]
    return create_kwargs


def _host_volume_from_bind(bind):
    drive, rest = ntpath.splitdrive(bind)
    bits = rest.split(':', 1)
    if len(bits) == 1 or bits[1] in ('ro', 'rw'):
        return drive + bits[0]
    else:
        return bits[1].rstrip(':ro').rstrip(':rw')
