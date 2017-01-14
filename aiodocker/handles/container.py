import asyncio
import ujson

from .handle import Handle
from ..records import Container


class ContainerHandles(Handle):
    # noinspection PyShadowingBuiltins
    @asyncio.coroutine
    def list(self, all=None, limit=None, since=None, before=None, size=None,
             filters=None):
        params = {}
        if all is not None:
            params['all'] = all
        if limit is not None:
            params['limit'] = limit
        if since is not None:
            params['since'] = since
        if before is not None:
            params['before'] = before
        if size is not None:
            params['size'] = size
        if filters is not None:
            params['filters'] = ujson.dumps(filters)

        response = yield from self.client.get(
            url=self.url('/containers/json'),
            params=params
        )
        self._check_status(response.status)
        details = yield from response.json(encoding='utf-8')  # type: list
        containers = []
        for brief in details:
            container = yield from self.get(id_name=brief.get('Id'))
            if container is not None:
                containers.append(container)
        return containers

    @asyncio.coroutine
    def create(self, name=None, hostname=None, domain_name=None, user=None,
               attach_stdin=None, attach_stdout=None, attach_stderr=None,
               tty=None, open_stdin=None, env=None, labels=None, cmd=None,
               entry_point=None, image=None, volumes=None, working_dir=None,
               network_disabled=None, exposed_ports=None, stop_signal=None,
               host_config=None):
        headers = {'Content-Type': 'application/json'}
        params = {'name': name} if name else {}
        payload = {}
        if hostname is not None:
            payload['Hostname'] = hostname
        if domain_name is not None:
            payload['Domainname'] = domain_name
        if user is not None:
            payload['User'] = user
        if attach_stdin is not None:
            payload['AttachStdin'] = attach_stdin
        if attach_stdout is not None:
            payload['AttachStdout'] = attach_stdout
        if attach_stderr is not None:
            payload['AttachStderr'] = attach_stderr
        if tty is not None:
            payload['Tty'] = tty
        if open_stdin is not None:
            payload['OpenStdin'] = open_stdin
        if env is not None:
            payload['Env'] = env
        if labels is not None:
            payload['Labels'] = labels
        if cmd is not None:
            payload['Cmd'] = cmd
        if entry_point is not None:
            payload['EntryPoint'] = entry_point
        if image is not None:
            payload['Image'] = image
        if volumes is not None:
            payload['Volumes'] = volumes
        if working_dir is not None:
            payload['WorkingDir'] = working_dir
        if network_disabled is not None:
            payload['NetworkDisabled'] = network_disabled
        if exposed_ports is not None:
            payload['ExposedPorts'] = exposed_ports
        if stop_signal is not None:
            payload['StopSignal'] = stop_signal
        if host_config is not None:
            payload['HostConfig'] = host_config

        response = yield from self.client.post(
            url=self.url('/containers/create'),
            headers=headers,
            params=params,
            data=ujson.dumps(payload)
        )
        self._check_status(response.status)
        brief = yield from response.json(encoding='utf-8')  # type: dict
        return (yield from self.get(id_name=brief.get('Id')))

    @asyncio.coroutine
    def inspect(self, id_name, size=None):
        params = {}
        if size is not None:
            params['size'] = size

        response = yield from self.client.get(
            url=self.url('/containers/{}/json'.format(id_name))
        )
        self._check_status(response.status)
        return (yield from response.json(encoding='utf-8'))

    @asyncio.coroutine
    def get(self, id_name):
        attrs = yield from self.inspect(id_name=id_name)
        if attrs is None:
            return None
        return Container(attrs=attrs, docker=self.docker)

    @asyncio.coroutine
    def top(self, id_name, ps_args=None):
        params = {}
        if ps_args is not None:
            params['ps_args'] = ps_args

        response = yield from self.client.get(
            url=self.url('/containers/{}/top'.format(id_name)),
            params=params
        )
        self._check_status(response.status)
        return (yield from response.json(encoding='utf-8'))

    @asyncio.coroutine
    def logs(self, id_name, details=None, follow=None, stdout=None, stderr=None,
             since=None, timestamps=None, tail=None):
        params = {}
        if details is not None:
            params['details'] = details
        if follow is not None:
            params['follow'] = follow
        if stdout is not None:
            params['stdout'] = stdout
        if stderr is not None:
            params['stderr'] = stderr
        if since is not None:
            params['since'] = since
        if timestamps is not None:
            params['timestamps'] = timestamps
        if tail is not None:
            params['tail'] = tail

        response = yield from self.client.get(
            url=self.url('/containers/{}/json'.format(id_name))
        )
        self._check_status(response.status)
        return (yield from response.json(encoding='utf-8'))

    @asyncio.coroutine
    def changes(self, id_name):
        response = yield from self.client.get(
            url=self.url('/containers/{}/changes'.format(id_name))
        )
        self._check_status(response.status)
        return (yield from response.json(encoding='utf-8'))

    @asyncio.coroutine
    def export(self, id_name):
        raise NotImplemented()

    @asyncio.coroutine
    def stats(self, id_name):
        raise NotImplemented()

    @asyncio.coroutine
    def resize(self, id_name, height, width):
        params = {"height": height, "width": width}
        response = yield from self.client.post(
            url=self.url('/containers/{}/resize'.format(id_name)),
            params=params
        )
        self._check_status(response.status)

    @asyncio.coroutine
    def start(self, id_name, detach_keys=None):
        params = {}
        if detach_keys is not None:
            params['detachKeys'] = detach_keys
        response = yield from self.client.post(
            url=self.url('/containers/{}/start'.format(id_name)),
            params=params
        )
        self._check_status(response.status)

    @asyncio.coroutine
    def stop(self, id_name, timeout=None):
        params = {}
        if timeout is not None:
            params['t'] = timeout
        response = yield from self.client.post(
            url=self.url('/containers/{}/stop'.format(id_name)),
            params=params
        )
        self._check_status(response.status)

    @asyncio.coroutine
    def restart(self, id_name, timeout=None):
        params = {}
        if timeout is not None:
            params['t'] = timeout
        response = yield from self.client.post(
            url=self.url('/containers/{}/stop'.format(id_name)),
            params=params
        )
        self._check_status(response.status)

    @asyncio.coroutine
    def kill(self, id_name, signal=None):
        params = {}
        if signal is not None:
            params['signal'] = signal
        response = yield from self.client.post(
            url=self.url('/containers/{}/kill'.format(id_name)),
            params=params
        )
        self._check_status(response.status)

    @asyncio.coroutine
    def update(self, id_name, block_io_weight=None, cpu_shares=None,
               cpu_period=None, cpu_quota=None, cpu_set_cpus=None,
               cpu_set_mems=None, memory=None, memory_swap=None,
               memory_reservation=None, kernel_memory=None,
               restart_policy=None):
        headers = {'Content-Type': 'application/json'}
        payload = {}
        if block_io_weight is not None:
            payload['BlkioWeight'] = block_io_weight
        if cpu_shares is not None:
            payload['CpuShares'] = cpu_shares
        if cpu_period is not None:
            payload['CpuPeriod'] = cpu_period
        if cpu_quota is not None:
            payload['CpuQuota'] = cpu_quota
        if cpu_set_cpus is not None:
            payload['CpusetCpus'] = cpu_set_cpus
        if cpu_set_mems is not None:
            payload['CpusetMems'] = cpu_set_mems
        if memory is not None:
            payload['Memory'] = memory
        if memory_swap is not None:
            payload['MemorySwap'] = memory_swap
        if memory_reservation is not None:
            payload['MemoryReservation'] = memory_reservation
        if kernel_memory is not None:
            payload['KernelMemory'] = kernel_memory
        if restart_policy is not None:
            payload['RestartPolicy'] = restart_policy
        response = yield from self.client.post(
            url=self.url('/containers/{}/update'.format(id_name)),
            headers=headers,
            data=ujson.dumps(payload)
        )
        self._check_status(response.status)
        return (yield from response.json(encoding='utf-8'))

    @asyncio.coroutine
    def rename(self, id_name, name=None):
        params = {}
        if name is not None:
            params['name'] = name
        response = yield from self.client.post(
            url=self.url('/containers/{}/rename'.format(id_name)),
            params=params
        )
        self._check_status(response.status)

    @asyncio.coroutine
    def pause(self, id_name):
        response = yield from self.client.post(
            url=self.url('/containers/{}/pause'.format(id_name))
        )
        self._check_status(response.status)

    @asyncio.coroutine
    def unpause(self, id_name):
        response = yield from self.client.post(
            url=self.url('/containers/{}/unpause'.format(id_name))
        )
        self._check_status(response.status)

    @asyncio.coroutine
    def attach(self, id_name):
        raise NotImplemented()

    @asyncio.coroutine
    def attach_ws(self, id_name):
        raise NotImplemented()

    @asyncio.coroutine
    def wait(self, id_name):
        response = yield from self.client.post(
            url=self.url('/containers/{}/wait'.format(id_name))
        )
        self._check_status(response.status)

    @asyncio.coroutine
    def remove(self, id_name, volumes=None, force=None):
        params = {}
        if volumes is not None:
            params['v'] = volumes
        if force is not None:
            params['force'] = force

        response = yield from self.client.delete(
            url=self.url('/containers/{}'.format(id_name)),
            params=params
        )
        self._check_status(response.status)
