import json
import tarfile
from typing import Any, List, Mapping

from ..exceptions import DockerError, DockerContainerError
from ..jsonstream import json_stream_result
from ..multiplexed import multiplexed_result
from ..utils import identical, parse_result, clean_filters
from ..types import ContainerConfig, HostConfig, NetworkingConfig, EndpointConfig

from ..logs import DockerLog


class DockerContainerAPI(object):
    def __init__(self, api_client):
        self.api_client = api_client

    async def list(self, all=False, limit=-1, size=False, filters: Mapping = None) -> List[Mapping]:
        """
        List containers. Similar to the ``docker ps`` command.

        Args:
            all (bool): Show all containers. Only running containers are shown
                by default
            limit (int): Show `limit` last created containers, include
                non-running ones
            size (bool): Display sizes
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
            A list of dicts, one per container

        Raises:
            :py:class:`aiodocker.errors.APIError`
                If the server returns an error.
        """
        params = {
            'limit': limit,
            'all': all,
            'size': size
        }
        if filters:
            params['filters'] = clean_filters(filters)
        response = await self.api_client._query_json(
            "containers/json",
            method='GET',
            params=params
        )
        return response

    async def create(self, image, command=None, hostname=None, user=None,
                     detach=False, stdin_open=False, tty=False, ports=None,
                     environment=None, volumes=None,
                     network_disabled=False, name=None, entrypoint=None,
                     working_dir=None, domainname=None, host_config=None,
                     mac_address=None, labels=None, stop_signal=None,
                     networking_config=None, healthcheck=None,
                     stop_timeout=None, runtime=None):
        """
        Creates a container. Parameters are similar to those for the ``docker
        run`` command except it doesn't support the attach options (``-a``).

        The arguments that are passed directly to this function are
        host-independent configuration options. Host-specific configuration
        is passed with the `host_config` argument. You'll normally want to
        use this method in combination with the :py:meth:`create_host_config`
        method to generate ``host_config``.

        **Port bindings**

        Port binding is done in two parts: first, provide a list of ports to
        open inside the container with the ``ports`` parameter, then declare
        bindings with the ``host_config`` parameter. For example:

        .. code-block:: python

            container_id = client.container.create(
                'busybox', 'ls', ports=[1111, 2222],
                host_config=client.container.create_host_config(port_bindings={
                    1111: 4567,
                    2222: None
                })
            )


        You can limit the host address on which the port will be exposed like
        such:

        .. code-block:: python

            client.container.create_host_config(port_bindings={1111: ('127.0.0.1', 4567)})

        Or without host port assignment:

        .. code-block:: python

            client.container.create_host_config(port_bindings={1111: ('127.0.0.1',)})

        If you wish to use UDP instead of TCP (default), you need to declare
        ports as such in both the config and host config:

        .. code-block:: python

            container_id = client.container.create(
                'busybox', 'ls', ports=[(1111, 'udp'), 2222],
                host_config = client.container.create_host_config(port_bindings={
                    '1111/udp': 4567, 2222: None
                })
            )

        To bind multiple host ports to a single container port, use the
        following syntax:

        .. code-block:: python

            client.container.create_host_config(port_bindings={
                1111: [1234, 4567]
            })

        You can also bind multiple IPs to a single container port:

        .. code-block:: python

            client.container.create_host_config(port_bindings={
                1111: [
                    ('192.168.0.100', 1234),
                    ('192.168.0.101', 1234)
                ]
            })

        **Using volumes**

        Volume declaration is done in two parts. Provide a list of
        paths to use as mountpoints inside the container with the
        ``volumes`` parameter, and declare mappings from paths on the host
        in the ``host_config`` section.

        .. code-block:: python

            container_id = client.container.create(
                'busybox', 'ls', volumes=['/mnt/vol1', '/mnt/vol2'],
                host_config=cli.create_host_config(binds={
                    '/home/user1/': {
                        'bind': '/mnt/vol2',
                        'mode': 'rw',
                    },
                    '/var/www': {
                        'bind': '/mnt/vol1',
                        'mode': 'ro',
                    }
                })
            )

        You can alternatively specify binds as a list. This code is equivalent
        to the example above:

        .. code-block:: python

            container_id = api.container.create(
                'busybox', 'ls', volumes=['/mnt/vol1', '/mnt/vol2'],
                host_config=cli.create_host_config(binds=[
                    '/home/user1/:/mnt/vol2',
                    '/var/www:/mnt/vol1:ro',
                ])
            )

        **Networking**

        You can specify networks to connect the container to by using the
        ``networking_config`` parameter. At the time of creation, you can
        only connect a container to a single networking, but you
        can create more connections by using
        :py:meth:`~connect_container_to_network`.

        For example:

        .. code-block:: python

            networking_config = api.container.create_networking_config({
                'network1': docker_client.create_endpoint_config(
                    ipv4_address='172.28.0.124',
                    aliases=['foo', 'bar'],
                    links=['container2']
                )
            })

            ctnr = api.container.create(
                img, command, networking_config=networking_config
            )

        Args:
            image (str): The image to run
            command (str or list): The command to be run in the container
            hostname (str): Optional hostname for the container
            user (str or int): Username or UID
            detach (bool): Detached mode: run container in the background and
                return container ID
            stdin_open (bool): Keep STDIN open even if not attached
            tty (bool): Allocate a pseudo-TTY
            ports (list of ints): A list of port numbers
            environment (dict or list): A dictionary or a list of strings in
                the following format ``["PASSWORD=xxx"]`` or
                ``{"PASSWORD": "xxx"}``.
            volumes (str or list): List of paths inside the container to use
                as volumes.
            network_disabled (bool): Disable networking
            name (str): A name for the container
            entrypoint (str or list): An entrypoint
            working_dir (str): Path to the working directory
            domainname (str): The domain name to use for the container
            host_config (dict): A dictionary created with
                :py:meth:`create_host_config`.
            mac_address (str): The Mac Address to assign the container
            labels (dict or list): A dictionary of name-value labels (e.g.
                ``{"label1": "value1", "label2": "value2"}``) or a list of
                names of labels to set with empty values (e.g.
                ``["label1", "label2"]``)
            stop_signal (str): The stop signal to use to stop the container
                (e.g. ``SIGINT``).
            stop_timeout (int): Timeout to stop the container, in seconds.
                Default: 10
            networking_config (dict): A networking configuration generated
                by :py:meth:`create_networking_config`.
            runtime (str): Runtime to use with this container.
            healthcheck (dict): Specify a test to perform to check that the
                container is healthy.

        Returns:
            A dictionary with an image 'Id' key and a 'Warnings' key.

        Raises:
            :py:class:`aiodocker.errors.ImageNotFound`
                If the specified image does not exist.
            :py:class:`aiodocker.errors.APIError`
                If the server returns an error.
        """
        if isinstance(volumes, str):
            volumes = [volumes, ]

        config = self.create_container_config(
            image, command, hostname, user, detach, stdin_open, tty,
            ports, environment, volumes,
            network_disabled, entrypoint, working_dir, domainname,
            host_config, mac_address, labels,
            stop_signal, networking_config, healthcheck,
            stop_timeout, runtime
        )
        return await self.create_from_config(config, name)

    def create_container_config(self, *args, **kwargs):
        return ContainerConfig(self.api_client.version, *args, **kwargs)

    async def create_from_config(self, config, name=None) -> Mapping[str, Any]:
        url = "containers/create"

        config = json.dumps(config, sort_keys=True).encode('utf-8')
        kwargs = {}
        if name:
            kwargs['name'] = name
        response = await self.api_client._query_json(
            url,
            method='POST',
            data=config,
            params=kwargs
        )
        return response

    def create_host_config(self, *args, **kwargs):
        """
        Create a dictionary for the ``host_config`` argument to
        :py:meth:`create`.

        Args:
            auto_remove (bool): enable auto-removal of the container on daemon
                side when the container's process exits.
            binds (dict): Volumes to bind. See :py:meth:`create_container`
                    for more information.
            blkio_weight_device: Block IO weight (relative device weight) in
                the form of: ``[{"Path": "device_path", "Weight": weight}]``.
            blkio_weight: Block IO weight (relative weight), accepts a weight
                value between 10 and 1000.
            cap_add (list of str): Add kernel capabilities. For example,
                ``["SYS_ADMIN", "MKNOD"]``.
            cap_drop (list of str): Drop kernel capabilities.
            cpu_period (int): The length of a CPU period in microseconds.
            cpu_quota (int): Microseconds of CPU time that the container can
                get in a CPU period.
            cpu_shares (int): CPU shares (relative weight).
            cpuset_cpus (str): CPUs in which to allow execution (``0-3``,
                ``0,1``).
            cpuset_mems (str): Memory nodes (MEMs) in which to allow execution
                (``0-3``, ``0,1``). Only effective on NUMA systems.
            device_cgroup_rules (:py:class:`list`): A list of cgroup rules to
                apply to the container.
            device_read_bps: Limit read rate (bytes per second) from a device
                in the form of: `[{"Path": "device_path", "Rate": rate}]`
            device_read_iops: Limit read rate (IO per second) from a device.
            device_write_bps: Limit write rate (bytes per second) from a
                device.
            device_write_iops: Limit write rate (IO per second) from a device.
            devices (:py:class:`list`): Expose host devices to the container,
                as a list of strings in the form
                ``<path_on_host>:<path_in_container>:<cgroup_permissions>``.

                For example, ``/dev/sda:/dev/xvda:rwm`` allows the container
                to have read-write access to the host's ``/dev/sda`` via a
                node named ``/dev/xvda`` inside the container.
            dns (:py:class:`list`): Set custom DNS servers.
            dns_opt (:py:class:`list`): Additional options to be added to the
                container's ``resolv.conf`` file
            dns_search (:py:class:`list`): DNS search domains.
            extra_hosts (dict): Addtional hostnames to resolve inside the
                container, as a mapping of hostname to IP address.
            group_add (:py:class:`list`): List of additional group names and/or
                IDs that the container process will run as.
            init (bool): Run an init inside the container that forwards
                signals and reaps processes
            init_path (str): Path to the docker-init binary
            ipc_mode (str): Set the IPC mode for the container.
            isolation (str): Isolation technology to use. Default: `None`.
            links (dict or list of tuples): Either a dictionary mapping name
                to alias or as a list of ``(name, alias)`` tuples.
            log_config (dict): Logging configuration, as a dictionary with
                keys:

                - ``type`` The logging driver name.
                - ``config`` A dictionary of configuration for the logging
                  driver.

            lxc_conf (dict): LXC config.
            mem_limit (float or str): Memory limit. Accepts float values
                (which represent the memory limit of the created container in
                bytes) or a string with a units identification char
                (``100000b``, ``1000k``, ``128m``, ``1g``). If a string is
                specified without a units character, bytes are assumed as an
            mem_swappiness (int): Tune a container's memory swappiness
                behavior. Accepts number between 0 and 100.
            memswap_limit (str or int): Maximum amount of memory + swap a
                container is allowed to consume.
            mounts (:py:class:`list`): Specification for mounts to be added to
                the container. More powerful alternative to ``binds``. Each
                item in the list is expected to be a
                :py:class:`docker.types.Mount` object.
            network_mode (str): One of:

                - ``bridge`` Create a new network stack for the container on
                  on the bridge network.
                - ``none`` No networking for this container.
                - ``container:<name|id>`` Reuse another container's network
                  stack.
                - ``host`` Use the host network stack.
            oom_kill_disable (bool): Whether to disable OOM killer.
            oom_score_adj (int): An integer value containing the score given
                to the container in order to tune OOM killer preferences.
            pid_mode (str): If set to ``host``, use the host PID namespace
                inside the container.
            pids_limit (int): Tune a container's pids limit. Set ``-1`` for
                unlimited.
            port_bindings (dict): See :py:meth:`create_container`
                    for more information.
            privileged (bool): Give extended privileges to this container.
            publish_all_ports (bool): Publish all ports to the host.
            read_only (bool): Mount the container's root filesystem as read
                only.
            restart_policy (dict): Restart the container when it exits.
                Configured as a dictionary with keys:

                - ``Name`` One of ``on-failure``, or ``always``.
                - ``MaximumRetryCount`` Number of times to restart the
                  container on failure.
            security_opt (:py:class:`list`): A list of string values to
                customize labels for MLS systems, such as SELinux.
            shm_size (str or int): Size of /dev/shm (e.g. ``1G``).
            storage_opt (dict): Storage driver options per container as a
                key-value mapping.
            sysctls (dict): Kernel parameters to set in the container.
            tmpfs (dict): Temporary filesystems to mount, as a dictionary
                mapping a path inside the container to options for that path.

                For example:

                .. code-block:: python

                    {
                        '/mnt/vol2': '',
                        '/mnt/vol1': 'size=3G,uid=1000'
                    }

            ulimits (:py:class:`list`): Ulimits to set inside the container,
                as a list of dicts.
            userns_mode (str): Sets the user namespace mode for the container
                when user namespace remapping option is enabled. Supported
                values are: ``host``
            volumes_from (:py:class:`list`): List of container names or IDs to
                get volumes from.
            runtime (str): Runtime to use with this container.


        Returns:
            (dict) A dictionary which can be passed to the ``host_config``
            argument to :py:meth:`create`.

        Example:

        .. code-block:: python

            api.container.create_host_config(privileged=True, cap_drop=['MKNOD'],
                                       volumes_from=['nostalgic_newton'])
            {'CapDrop': ['MKNOD'], 'LxcConf': None, 'Privileged': True,
             'VolumesFrom': ['nostalgic_newton'], 'PublishAllPorts': False}

        """
        if not kwargs:
            kwargs = {}
        if 'version' in kwargs:
            raise TypeError(
                "create_host_config() got an unexpected "
                "keyword argument 'version'"
            )
        kwargs['version'] = self.api_client.version
        return HostConfig(*args, **kwargs)

    def create_networking_config(self, *args, **kwargs):
        """
        Create a networking config dictionary to be used as the
        ``networking_config`` parameter in :py:meth:`create`.

        Args:
            endpoints_config (dict): A dictionary mapping network names to
                endpoint configurations generated by
                :py:meth:`create_endpoint_config`.

        Returns:
            (dict) A networking config.

        Example:

        .. code-block:: python

            api.container.create_network('network1')
            networking_config = api.container.create_networking_config({
                'network1': api.container.create_endpoint_config()
            })
            container = api.container.create(
                img, command, networking_config=networking_config
            )

        """
        return NetworkingConfig(*args, **kwargs)

    def create_endpoint_config(self, *args, **kwargs):
        """
        Create an endpoint config dictionary to be used with
        :py:meth:`create_networking_config`.

        Args:
            aliases (:py:class:`list`): A list of aliases for this endpoint.
                Names in that list can be used within the network to reach the
                container. Defaults to ``None``.
            links (:py:class:`list`): A list of links for this endpoint.
                Containers declared in this list will be linked to this
                container. Defaults to ``None``.
            ipv4_address (str): The IP address of this container on the
                network, using the IPv4 protocol. Defaults to ``None``.
            ipv6_address (str): The IP address of this container on the
                network, using the IPv6 protocol. Defaults to ``None``.
            link_local_ips (:py:class:`list`): A list of link-local (IPv4/IPv6)
                addresses.

        Returns:
            (dict) An endpoint config.

        Example:

        .. code-block:: python

            endpoint_config = api.container.create_endpoint_config(
                aliases=['web', 'app'],
                links=['app_db'],
                ipv4_address='132.65.0.123'
            )

        """
        return EndpointConfig(self.api_client.version, *args, **kwargs)

    async def remove(self, container, v=False, link=False, force=False):
        """
        Remove a container. Similar to the ``docker rm`` command.

        Args:
            container (str): The container to remove
            v (bool): Remove the volumes associated with the container
            link (bool): Remove the specified link and not the underlying
                container
            force (bool): Force the removal of a running container (uses
                ``SIGKILL``)

        Raises:
            :py:class:`aiodocker.errors.APIError`
                If the server returns an error.
        """
        params = {
            'v': v,
            'link': link,
            'force': force
        }

        response = await self.api_client._query(
            "containers/{id}".format(id=container),
            method='DELETE',
            params=params
        )
        await response.release()
        return

    async def inspect(self, container_id, size=False) -> Mapping[str, Any]:
        params = {
            'size': size
        }
        response = await self.api_client._query_json(
            "containers/{id}/json".format(id=container_id),
            method='GET',
            params=params
        )
        return response

    async def logs(self, container_id, stdout=False, stderr=False, follow=False, **kwargs):
        if stdout is False and stderr is False:
            raise TypeError("Need one of stdout or stderr")

        params = {
            "stdout": stdout,
            "stderr": stderr,
            "follow": follow,
        }
        params.update(kwargs)

        inspect_info = await self.inspect(container_id)
        is_tty = inspect_info['Config']['Tty']

        response = await self.api_client._query(
            "containers/{id}/logs".format(id=container_id),
            method='GET',
            params=params,
        )
        return await multiplexed_result(response, follow, is_tty=is_tty)

    async def prune(self, filters: Mapping = None) -> Mapping[str, Any]:
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
        params = {}
        if filters:
            params['filters'] = clean_filters(filters)
        response = await self.api_client._query_json(
            "containers/prune",
            method='POST',
            params=params
        )
        return response

    async def restart(self, container_id, timeout=None):
        params = {}
        if timeout is not None:
            params['t'] = timeout
        response = await self.api_client._query(
            "containers/{id}/restart".format(id=container_id),
            method='POST',
            params=params
        )
        await response.release()
        return

    async def start(self, container_id):
        response = await self.api_client._query(
            "containers/{}/start".format(container_id),
            method='POST'
        )
        await response.release()
        return

    async def stop(self, container_id, **kwargs):
        response = await self.api_client._query(
            "containers/{id}/stop".format(id=container_id),
            method='POST',
            params=kwargs
        )
        await response.release()
        return

    async def wait(self, container_id, timeout=None, **kwargs):
        data = await self.api_client._query_json(
            "containers/{id}/wait".format(id=container_id),
            method='POST',
            params=kwargs,
            timeout=timeout,
        )
        return data
