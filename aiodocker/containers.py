import json
import tarfile

from .exceptions import DockerError, DockerContainerError
from .jsonstream import json_stream_result
from .multiplexed import multiplexed_result
from .utils import identical, parse_result

from .logs import DockerLog


class DockerContainers(object):
    def __init__(self, docker):
        self.docker = docker

    async def list(self, **kwargs):
        data = await self.docker._query_json(
            "containers/json",
            method='GET',
            params=kwargs
        )
        return [DockerContainer(self.docker, **x) for x in data]

    async def create_or_replace(self, name, config):
        container = None

        try:
            container = await self.get(name)
            if not identical(config, container._container):
                running = container._container.get(
                    "State", {}).get("Running", False)
                if running:
                    await container.stop()
                await container.delete()
                container = None
        except DockerError:
            pass

        if container is None:
            container = await self.create(config, name=name)

        return container

    async def create(self, config, *, name=None):
        url = "containers/create"

        config = json.dumps(config, sort_keys=True).encode('utf-8')
        kwargs = {}
        if name:
            kwargs['name'] = name
        data = await self.docker._query_json(
            url,
            method='POST',
            data=config,
            params=kwargs
        )
        return DockerContainer(self.docker, id=data['Id'])

    async def run(self, config, *, name=None):
        """
        Create and start a container.

        If container.start() will raise an error the exception will contain
        a `container_id` attribute with the id of the container.
        """
        try:
            container = await self.create(config, name=name)
        except DockerError as err:
            # image not find, try pull it
            if err.status == 404 and 'Image' in config:
                await self.docker.pull(config['Image'])
                container = await self.create(config, name=name)
            else:
                raise err

        try:
            await container.start()
        except DockerError as err:
            raise DockerContainerError(
                err.status,
                {"message": err.message},
                container['id'])

        return container

    async def get(self, container, **kwargs):
        data = await self.docker._query_json(
            "containers/{container}/json".format(container=container),
            method='GET',
            params=kwargs
        )
        return DockerContainer(self.docker, **data)

    def container(self, container_id, **kwargs):
        data = {
            'id': container_id
        }
        data.update(kwargs)
        return DockerContainer(self.docker, **data)


class DockerContainer:
    def __init__(self, docker, **kwargs):
        self.docker = docker
        self._container = kwargs
        self._id = self._container.get("id", self._container.get(
            "ID", self._container.get("Id")))
        self.logs = DockerLog(docker, self)

    async def log(self, *, stdout=False, stderr=False, follow=False, **kwargs):
        if stdout is False and stderr is False:
            raise TypeError("Need one of stdout or stderr")

        params = {
            "stdout": stdout,
            "stderr": stderr,
            "follow": follow,
        }
        params.update(kwargs)

        inspect_info = await self.show()
        is_tty = inspect_info['Config']['Tty']

        response = await self.docker._query(
            "containers/{self._id}/logs".format(self=self),
            method='GET',
            params=params,
        )
        return await multiplexed_result(response, follow, is_tty=is_tty)

    async def copy(self, resource, **kwargs):
        # TODO: this is deprecated, use get_archive instead
        request = json.dumps({
            "Resource": resource,
        }, sort_keys=True).encode('utf-8')
        data = await self.docker._query(
            "containers/{self._id}/copy".format(self=self),
            method='POST',
            data=request,
            headers={"content-type": "application/json"},
            params=kwargs
        )
        return data

    async def get_archive(self, path: str) -> tarfile.TarFile:
        response = await self.docker._query(
            "containers/{self._id}/archive".format(self=self),
            method='GET',
            params={'path': path}
        )
        data = await parse_result(response)
        return data

    async def put_archive(self, path, data):
        response = await self.docker._query(
            "containers/{self._id}/archive".format(self=self),
            method='PUT',
            data=data,
            headers={"content-type": "application/json"},
            params={'path': path}
        )
        data = await parse_result(response)
        return data

    async def show(self, **kwargs):
        data = await self.docker._query_json(
            "containers/{self._id}/json".format(self=self),
            method='GET',
            params=kwargs
        )
        self._container = data
        return data

    async def stop(self, **kwargs):
        response = await self.docker._query(
            "containers/{self._id}/stop".format(self=self),
            method='POST',
            params=kwargs
        )
        await response.release()
        return

    async def start(self, **kwargs):
        response = await self.docker._query(
            "containers/{self._id}/start".format(self=self),
            method='POST',
            headers={"content-type": "application/json"},
            data=kwargs
        )
        await response.release()
        return

    async def kill(self, **kwargs):
        response = await self.docker._query(
            "containers/{self._id}/kill".format(self=self),
            method='POST',
            params=kwargs
        )
        await response.release()
        return

    async def wait(self, *, timeout=None, **kwargs):
        data = await self.docker._query_json(
            "containers/{self._id}/wait".format(self=self),
            method='POST',
            params=kwargs,
            timeout=timeout,
        )
        return data

    async def delete(self, **kwargs):
        response = await self.docker._query(
            "containers/{self._id}".format(self=self),
            method='DELETE',
            params=kwargs
        )
        await response.release()
        return

    async def websocket(self, **params):
        path = "containers/{self._id}/attach/ws".format(self=self)
        ws = await self.docker._websocket(path, **params)
        return ws

    async def port(self, private_port):
        if 'NetworkSettings' not in self._container:
            await self.show()

        private_port = str(private_port)
        h_ports = None

        # Port settings is None when the container is running with
        # network_mode=host.
        port_settings = self._container.get('NetworkSettings', {}).get('Ports')
        if port_settings is None:
            return None

        if '/' in private_port:
            return port_settings.get(private_port)

        h_ports = port_settings.get(private_port + '/tcp')
        if h_ports is None:
            h_ports = port_settings.get(private_port + '/udp')

        return h_ports

    async def stats(self, *, stream=True):
        if stream:
            response = await self.docker._query(
                "containers/{self._id}/stats".format(self=self),
                params={'stream': '1'},
            )
            return (await json_stream_result(response))
        else:
            data = await self.docker._query_json(
                "containers/{self._id}/stats".format(self=self),
                params={'stream': '0'},
            )
            return data

    def __getitem__(self, key):
        return self._container[key]

    def __hasitem__(self, key):
        return key in self._container
