import json
import shlex
import tarfile
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple, Union

from multidict import MultiDict
from yarl import URL

from .exceptions import DockerContainerError, DockerError
from .execs import Exec
from .jsonstream import json_stream_list, json_stream_stream
from .logs import DockerLog
from .multiplexed import multiplexed_result_list, multiplexed_result_stream
from .stream import Stream
from .utils import identical, parse_result


class DockerContainers(object):
    def __init__(self, docker):
        self.docker = docker

    async def list(self, **kwargs):
        data = await self.docker._query_json(
            "containers/json", method="GET", params=kwargs
        )
        return [DockerContainer(self.docker, **x) for x in data]

    async def create_or_replace(self, name, config):
        container = None

        try:
            container = await self.get(name)
            if not identical(config, container._container):
                running = container._container.get("State", {}).get("Running", False)
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

        config = json.dumps(config, sort_keys=True).encode("utf-8")
        kwargs = {}
        if name:
            kwargs["name"] = name
        data = await self.docker._query_json(
            url, method="POST", data=config, params=kwargs
        )
        return DockerContainer(self.docker, id=data["Id"])

    async def run(
        self,
        config,
        *,
        auth: Optional[Union[Mapping, str, bytes]] = None,
        name: Optional[str] = None,
    ):
        """
        Create and start a container.

        If container.start() will raise an error the exception will contain
        a `container_id` attribute with the id of the container.

        Use `auth` for specifying credentials for pulling absent image from
        a private registry.
        """
        try:
            container = await self.create(config, name=name)
        except DockerError as err:
            # image not fount, try pulling it
            if err.status == 404 and "Image" in config:
                await self.docker.pull(config["Image"], auth=auth)
                container = await self.create(config, name=name)
            else:
                raise err

        try:
            await container.start()
        except DockerError as err:
            raise DockerContainerError(
                err.status, {"message": err.message}, container["id"]
            )

        return container

    async def get(self, container, **kwargs):
        data = await self.docker._query_json(
            "containers/{container}/json".format(container=container),
            method="GET",
            params=kwargs,
        )
        return DockerContainer(self.docker, **data)

    def container(self, container_id, **kwargs):
        data = {"id": container_id}
        data.update(kwargs)
        return DockerContainer(self.docker, **data)

    def exec(self, exec_id: str) -> Exec:
        """Return Exec instance for already created exec object."""
        return Exec(self.docker, exec_id, None)


class DockerContainer:
    def __init__(self, docker, **kwargs):
        self.docker = docker
        self._container = kwargs
        self._id = self._container.get(
            "id", self._container.get("ID", self._container.get("Id"))
        )
        self.logs = DockerLog(docker, self)

    @property
    def id(self) -> str:
        return self._id

    def log(self, *, stdout=False, stderr=False, follow=False, **kwargs):
        if stdout is False and stderr is False:
            raise TypeError("Need one of stdout or stderr")

        params = {"stdout": stdout, "stderr": stderr, "follow": follow}
        params.update(kwargs)

        cm = self.docker._query(
            "containers/{self._id}/logs".format(self=self), method="GET", params=params
        )

        if follow:
            return self._logs_stream(cm)
        else:
            return self._logs_list(cm)

    async def _logs_stream(self, cm):
        inspect_info = await self.show()
        is_tty = inspect_info["Config"]["Tty"]

        async with cm as response:
            async for item in multiplexed_result_stream(response, is_tty=is_tty):
                yield item

    async def _logs_list(self, cm):
        inspect_info = await self.show()
        is_tty = inspect_info["Config"]["Tty"]

        async with cm as response:
            return await multiplexed_result_list(response, is_tty=is_tty)

    async def get_archive(self, path: str) -> tarfile.TarFile:
        async with self.docker._query(
            "containers/{self._id}/archive".format(self=self),
            method="GET",
            params={"path": path},
        ) as response:
            data = await parse_result(response)
            return data

    async def put_archive(self, path, data):
        async with self.docker._query(
            "containers/{self._id}/archive".format(self=self),
            method="PUT",
            data=data,
            headers={"content-type": "application/json"},
            params={"path": path},
        ) as response:
            data = await parse_result(response)
            return data

    async def show(self, **kwargs):
        data = await self.docker._query_json(
            "containers/{self._id}/json".format(self=self), method="GET", params=kwargs
        )
        self._container = data
        return data

    async def stop(self, **kwargs):
        async with self.docker._query(
            "containers/{self._id}/stop".format(self=self), method="POST", params=kwargs
        ):
            pass

    async def start(self, **kwargs):
        async with self.docker._query(
            "containers/{self._id}/start".format(self=self),
            method="POST",
            headers={"content-type": "application/json"},
            data=kwargs,
        ):
            pass

    async def restart(self, timeout=None):
        params = {}
        if timeout is not None:
            params["t"] = timeout
        async with self.docker._query(
            "containers/{self._id}/restart".format(self=self),
            method="POST",
            params=params,
        ):
            pass

    async def kill(self, **kwargs):
        async with self.docker._query(
            "containers/{self._id}/kill".format(self=self), method="POST", params=kwargs
        ):
            pass

    async def wait(self, *, timeout=None, **kwargs):
        data = await self.docker._query_json(
            "containers/{self._id}/wait".format(self=self),
            method="POST",
            params=kwargs,
            timeout=timeout,
        )
        return data

    async def delete(self, **kwargs):
        async with self.docker._query(
            "containers/{self._id}".format(self=self), method="DELETE", params=kwargs
        ):
            pass

    async def rename(self, newname):
        async with self.docker._query(
            "containers/{self._id}/rename".format(self=self),
            method="POST",
            headers={"content-type": "application/json"},
            params={"name": newname},
        ):
            pass

    async def websocket(self, **params):
        if not params:
            params = {"stdin": True, "stdout": True, "stderr": True, "stream": True}
        path = "containers/{self._id}/attach/ws".format(self=self)
        ws = await self.docker._websocket(path, **params)
        return ws

    def attach(
        self,
        *,
        stdout: bool = False,
        stderr: bool = False,
        stdin: bool = False,
        detach_keys: Optional[str] = None,
        logs: bool = False,
    ) -> Stream:
        async def setup() -> Tuple[URL, Optional[bytes], bool]:
            params: MultiDict[Union[str, int]] = MultiDict()
            if detach_keys:
                params.add("detachKeys", detach_keys)
            else:
                params.add("detachKeys", "")
            params.add("logs", int(logs))
            params.add("stdin", int(stdin))
            params.add("stdout", int(stdout))
            params.add("stderr", int(stderr))
            params.add("stream", 1)
            inspect_info = await self.show()
            return (
                URL(f"containers/{self._id}/attach").with_query(params),
                None,
                inspect_info["Config"]["Tty"],
            )

        return Stream(self.docker, setup, None)

    async def port(self, private_port):
        if "NetworkSettings" not in self._container:
            await self.show()

        private_port = str(private_port)
        h_ports = None

        # Port settings is None when the container is running with
        # network_mode=host.
        port_settings = self._container.get("NetworkSettings", {}).get("Ports")
        if port_settings is None:
            return None

        if "/" in private_port:
            return port_settings.get(private_port)

        h_ports = port_settings.get(private_port + "/tcp")
        if h_ports is None:
            h_ports = port_settings.get(private_port + "/udp")

        return h_ports

    def stats(self, *, stream=True):
        cm = self.docker._query(
            "containers/{self._id}/stats".format(self=self),
            params={"stream": "1" if stream else "0"},
        )
        if stream:
            return self._stats_stream(cm)
        else:
            return self._stats_list(cm)

    async def _stats_stream(self, cm):
        async with cm as response:
            async for item in json_stream_stream(response):
                yield item

    async def _stats_list(self, cm):
        async with cm as response:
            return await json_stream_list(response)

    async def exec(
        self,
        cmd: Union[str, Sequence[str]],
        stdout: bool = True,
        stderr: bool = True,
        stdin: bool = False,
        tty: bool = False,
        privileged: bool = False,
        user: str = "",  # root by default
        environment: Optional[Union[Mapping[str, str], Sequence[str]]] = None,
        workdir: Optional[str] = None,
        detach_keys: Optional[str] = None,
    ):
        if isinstance(cmd, str):
            cmd = shlex.split(cmd)
        if environment is None:
            pass
        elif isinstance(environment, Mapping):
            environment = [f"{key}={value}" for key, value in environment.items()]
        else:
            environment = list(environment)
        data = {
            "Container": self._id,
            "Privileged": privileged,
            "Tty": tty,
            "AttachStdin": stdin,
            "AttachStdout": stdout,
            "AttachStderr": stderr,
            "Cmd": cmd,
            "Env": environment,
        }

        if workdir is not None:
            data["WorkingDir"] = workdir
        else:
            data["WorkingDir"] = ""

        if detach_keys:
            data["detachKeys"] = detach_keys
        else:
            data["detachKeys"] = ""

        if user:
            data["User"] = user
        else:
            data["User"] = ""

        data = await self.docker._query_json(
            f"containers/{self._id}/exec", method="POST", data=data
        )
        return Exec(self.docker, data["Id"], tty=tty)

    async def resize(self, *, h: int, w: int) -> None:
        url = URL(f"containers/{self._id}/resize").with_query(h=h, w=w)
        await self.docker._query_json(url, method="POST")

    async def commit(
        self,
        *,
        repository: Optional[str] = None,
        tag: Optional[str] = None,
        message: Optional[str] = None,
        author: Optional[str] = None,
        changes: Optional[Union[str, Sequence[str]]] = None,
        config: Optional[Dict[str, Any]] = None,
        pause: bool = True,
    ) -> Dict[str, Any]:
        """
        Commit a container to an image. Similar to the ``docker commit``
        command.
        """
        params = {"container": self._id, "pause": pause}
        if repository is not None:
            params["repo"] = repository
        if tag is not None:
            params["tag"] = tag
        if message is not None:
            params["comment"] = message
        if author is not None:
            params["author"] = author
        if changes is not None:
            if not isinstance(changes, str):
                changes = "\n".join(changes)
            params["changes"] = changes

        return await self.docker._query_json(
            "commit", method="POST", params=params, data=config
        )

    async def pause(self) -> None:
        async with self.docker._query(f"containers/{self._id}/pause", method="POST"):
            pass

    async def unpause(self) -> None:
        async with self.docker._query(f"containers/{self._id}/unpause", method="POST"):
            pass

    def __getitem__(self, key):
        return self._container[key]

    def __hasitem__(self, key):
        return key in self._container
