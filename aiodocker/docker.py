import asyncio
import os
import ssl
from urllib.parse import urlparse, urlunparse

import aiohttp

from .handles import ImageHandles


class Docker:
    def __init__(self, host=None, verify_ssl=None, fingerprint=None,
                 use_dns_cache=True, family=0, ssl_context=None,
                 local_addr=None, resolver=None, conn_timeout=None,
                 keepalive_timeout=30, limit=None, force_close=False,
                 loop=None):
        if loop is None:
            loop = asyncio.get_event_loop()

        if host is None:
            host = os.environ.get('DOCKER_HOST', '/var/run/docker.sock')

        parts = urlparse(host)
        if parts.scheme in ('tcp', 'http', 'https'):
            if verify_ssl is None:
                verify_ssl = bool(os.environ.get('DOCKER_TLS_VERIFY', True))
            cert_path = os.environ.get('DOCKER_CERT_PATH')
            enable_ssl = cert_path or verify_ssl

            if enable_ssl:
                # noinspection PyUnresolvedReferences
                ssl_context = ssl.SSLContext(protocol=ssl.PROTOCOL_TLSv1)
                ssl_context.load_cert_chain(
                    certfile=os.path.join(cert_path, 'cert.pem'),
                    keyfile=os.path.join(cert_path, 'key.pem')
                )
                ssl_context.load_verify_locations(
                    cafile=os.path.join(cert_path, 'ca.pem')
                )

            connector = aiohttp.TCPConnector(
                verify_ssl=verify_ssl,
                fingerprint=fingerprint,
                use_dns_cache=use_dns_cache,
                family=family,
                ssl_context=ssl_context,
                local_addr=local_addr,
                resolver=resolver,
                conn_timeout=conn_timeout,
                keepalive_timeout=keepalive_timeout,
                limit=limit,
                force_close=force_close,
                loop=loop
            )

            parts.scheme = 'https' if enable_ssl else parts.scheme
            host = urlunparse((parts.scheme, parts.netloc, '', '', '', ''))
        else:
            connector = aiohttp.UnixConnector(
                path=host,
                conn_timeout=conn_timeout,
                keepalive_timeout=keepalive_timeout,
                limit=limit,
                force_close=force_close,
                loop=loop
            )
            host = 'http://localhost'

        self._loop = loop
        self._host = host
        self._connector = connector
        self._client = None

        if self._loop.is_running():
            self._client = aiohttp.ClientSession(connector=connector)
        else:
            # In case Docker instance is created during __init__
            @asyncio.coroutine
            def _start():
                return aiohttp.ClientSession(connector=self.connector)

            self._client = loop.run_until_complete(_start())

    def close(self):
        self._client.close()

    @property
    def loop(self):
        return self._loop

    @property
    def host(self):
        return self._host

    @property
    def connector(self):
        return self._connector

    @property
    def client(self):
        return self._client

    # @property
    # def containers(self):
    #     return ContainerCollection(client=self)

    @property
    def images(self):
        return ImageHandles(docker=self)

        # @asyncio.coroutine
        # def pull(self, image, stream=False):
        #     response = yield from self._query(
        #         "images/create", "POST",
        #         params={"fromImage": image},
        #         headers={"content-type": "application/json", },
        #     )
        #     json_stream = self._json_stream_result(response)
        #     if stream:
        #         return json_stream
        #     data = []
        #     i = yield from json_stream.__aiter__()
        #     while True:
        #         try:
        #             line = yield from i.__anext__()
        #         except StopAsyncIteration:
        #             break
        #         else:
        #             data.append(line)
        #
        #     return data
        #
        # def _endpoint(self, path):
        #     return "/".join([self.url, path])
        #
        # @asyncio.coroutine
        # def _query(self, path, method='GET', params=None, timeout=None,
        #            data=None, headers=None, **kwargs):
        #     url = self._endpoint(path)
        #     future = asyncio.ensure_future(self.session.request(
        #         method, url,
        #         params=params, headers=headers, data=data, **kwargs))
        #
        #     if timeout:
        #         response = yield from asyncio.wait_for(future, timeout)
        #     else:
        #         response = yield from future
        #
        #     if (response.status // 100) in [4, 5]:
        #         what = yield from response.read()
        #         response.close()
        #         raise ValueError("Got a failure from the server: '%s'" % (
        #             what.decode('utf-8').strip()
        #         ))
        #
        #     return response
        #
        # @asyncio.coroutine
        # def _result(self, response, response_type=None):
        #     if not response_type:
        #         ct = response.headers.get("Content-Type", "")
        #         if 'json' in ct:
        #             response_type = 'json'
        #         elif 'x-tar' in ct:
        #             response_type = 'tar'
        #         elif 'text/plain' in ct:
        #             response_type = 'text'
        #         else:
        #             raise TypeError("Unrecognized response type: {}".format(ct))
        #     if 'tar' == response_type:
        #         what = yield from response.read()
        #         yield from response.release()
        #         return tarfile.open(mode='r', fileobj=io.BytesIO(what))
        #
        #     if 'json' == response_type:
        #         data = yield from response.json(encoding='utf-8')
        #     elif 'text' == response_type:
        #         data = yield from response.text(encoding='utf-8')
        #     else:
        #         data = yield from response.read()
        #
        #     yield from response.release()
        #     return data
        #
        # def _json_stream_result(self, response, transform=None):
        #     return JsonStreamResult(response, transform)
        #
        # def _multiplexed_result(self, response):
        #     return MultiplexedResult(response)
        #
        # @asyncio.coroutine
        # def _websocket(self, url, **params):
        #     if not params:
        #         params = {
        #             'stdout': 1,
        #             'stderr': 1,
        #             'stream': 1
        #         }
        #     url = self._endpoint(url) + "?" + urllib.parse.urlencode(params)
        #     ws = yield from aiohttp.ws_connect(url, connector=self.connector)
        #     return ws
        #
        # @asyncio.coroutine
        # def _query_json(self, *args, **kwargs):
        #     response = yield from self._query(*args, **kwargs)
        #     data = yield from self._result(response, 'json')
        #     return data

# class DockerContainers(object):
#     def __init__(self, docker):
#         self.docker = docker
#
#     @asyncio.coroutine
#     def list(self, **kwargs):
#         data = yield from self.docker._query_json(
#             "containers/json",
#             method='GET',
#             params=kwargs
#         )
#         return [DockerContainer(self.docker, **x) for x in data]
#
#     @asyncio.coroutine
#     def create_or_replace(self, name, config):
#         container = None
#
#         try:
#             container = yield from self.get(name)
#             if not identical(config, container._container):
#                 running = container._container.get(
#                     "State", {}).get("Running", False)
#                 if running:
#                     yield from container.stop()
#                 yield from container.delete()
#                 container = None
#         except ValueError:
#             pass
#
#         if container is None:
#             container = yield from self.create(config, name=name)
#
#         return container
#
#     @asyncio.coroutine
#     def create(self, config, name=None):
#         url = "containers/create"
#
#         config = json.dumps(config, sort_keys=True, indent=4).encode('utf-8')
#         kwargs = {}
#         if name:
#             kwargs['name'] = name
#         data = yield from self.docker._query_json(
#             url,
#             method='POST',
#             headers={"content-type": "application/json", },
#             data=config,
#             params=kwargs
#         )
#         return DockerContainer(self.docker, id=data['Id'])
#
#     @asyncio.coroutine
#     def get(self, container, **kwargs):
#         data = yield from self.docker._query_json(
#             "containers/{}/json".format(container),
#             method='GET',
#             params=kwargs
#         )
#         return DockerContainer(self.docker, **data)
#
#     def container(self, container_id, **kwargs):
#         data = {
#             'id': container_id
#         }
#         data.update(kwargs)
#         return DockerContainer(self.docker, **data)
#
#
# class DockerContainer:
#     def __init__(self, docker, **kwargs):
#         self.docker = docker
#         self._container = kwargs
#         self._id = self._container.get("id", self._container.get(
#             "ID", self._container.get("Id")))
#         self.logs = DockerLog(docker, self)
#
#     @asyncio.coroutine
#     def log(self, stdout=False, stderr=False, follow=False, **kwargs):
#         if stdout is False and stderr is False:
#             raise TypeError("Need one of stdout or stderr")
#
#         params = {
#             "stdout": stdout,
#             "stderr": stderr,
#             "follow": follow,
#         }
#         params.update(kwargs)
#
#         response = yield from self.docker._query(
#             "containers/{}/logs".format(self._id),
#             method='GET',
#             params=params,
#         )
#         log_stream = self.docker._multiplexed_result(response)
#         if follow:
#             return log_stream
#         log_lines = []
#
#         # TODO 3.5 cleans up this syntax
#         i = yield from log_stream.__aiter__()
#         while True:
#             try:
#                 line = yield from i.__anext__()
#             except StopAsyncIteration:
#                 break
#             else:
#                 log_lines.append(line.decode('utf-8'))
#
#         return ''.join(log_lines)
#
#     @asyncio.coroutine
#     def copy(self, resource, **kwargs):
#         # TODO this is deprecated, use get_archive instead
#         request = json.dumps({
#             "Resource": resource,
#         }, sort_keys=True, indent=4).encode('utf-8')
#         data = yield from self.docker._query(
#             "containers/{}/copy".format(self._id),
#             method='POST',
#             data=request,
#             headers={"content-type": "application/json", },
#             params=kwargs
#         )
#         return data
#
#     @asyncio.coroutine
#     def put_archive(self, path, data):
#         response = yield from self.docker._query(
#             "containers/{}/archive".format(self._id),
#             method='PUT',
#             data=data,
#             headers={"content-type": "application/json", },
#             params={'path': path}
#         )
#         data = yield from self.docker._result(response)
#         return data
#
#     @asyncio.coroutine
#     def show(self, **kwargs):
#         data = yield from self.docker._query_json(
#             "containers/{}/json".format(self._id),
#             method='GET',
#             params=kwargs
#         )
#         self._container = data
#         return data
#
#     @asyncio.coroutine
#     def stop(self, **kwargs):
#         response = yield from self.docker._query(
#             "containers/{}/stop".format(self._id),
#             method='POST',
#             params=kwargs
#         )
#         yield from response.release()
#         return
#
#     @asyncio.coroutine
#     def start(self, _config=None, **config):
#         config = _config or config
#         config = json.dumps(config, sort_keys=True, indent=4).encode('utf-8')
#         response = yield from self.docker._query(
#             "containers/{}/start".format(self._id),
#             method='POST',
#             headers={"content-type": "application/json", },
#             data=config
#         )
#         yield from response.release()
#         return
#
#     @asyncio.coroutine
#     def kill(self, **kwargs):
#         data = yield from self.docker._query_json(
#             "containers/{}/kill".format(self._id),
#             method='POST',
#             params=kwargs
#         )
#         return data
#
#     @asyncio.coroutine
#     def wait(self, timeout=None, **kwargs):
#         data = yield from self.docker._query_json(
#             "containers/{}/wait".format(self._id),
#             method='POST',
#             params=kwargs,
#             timeout=timeout,
#         )
#         return data
#
#     @asyncio.coroutine
#     def delete(self, **kwargs):
#         response = yield from self.docker._query(
#             "containers/{}".format(self._id),
#             method='DELETE',
#             params=kwargs
#         )
#         yield from response.release()
#         return
#
#     @asyncio.coroutine
#     def websocket(self, **params):
#         url = "containers/{}/attach/ws".format(self._id)
#         ws = yield from self.docker._websocket(url, **params)
#         return ws
#
#     @asyncio.coroutine
#     def port(self, private_port):
#         if 'NetworkSettings' not in self._container:
#             yield from self.show()
#
#         private_port = str(private_port)
#         h_ports = None
#
#         # Port settings is None when the container is running with
#         # network_mode=host.
#         port_settings = self._container.get('NetworkSettings', {}).get('Ports')
#         if port_settings is None:
#             return None
#
#         if '/' in private_port:
#             return port_settings.get(private_port)
#
#         h_ports = port_settings.get(private_port + '/tcp')
#         if h_ports is None:
#             h_ports = port_settings.get(private_port + '/udp')
#
#         return h_ports
#
#     def __getitem__(self, key):
#         return self._container[key]
#
#     def __hasitem__(self, key):
#         return key in self._container
#
#
# class DockerEvents:
#     def __init__(self, docker):
#         self.running = False
#         self.docker = docker
#         self.channel = Channel()
#
#     def listen(self):
#         return self.channel.listen()
#
#     def saferun(self):
#         if self.running:
#             return
#         self.running = True
#         asyncio.async(self.run())
#
#     @asyncio.coroutine
#     def query(self, **params):
#         response = yield from self.docker._query(
#             "events",
#             method="GET",
#             params=params,
#         )
#         json_stream = self.docker._json_stream_result(response,
#                                                       self._transform_event)
#         return json_stream
#
#     def _transform_event(self, data):
#         if 'time' in data:
#             data['time'] = dt.datetime.fromtimestamp(data['time'])
#         return data
#
#     @asyncio.coroutine
#     def run(self):
#         self.running = True
#         containers = self.docker.containers
#         json_stream = yield from self.query()
#
#         i = yield from json_stream.__aiter__()
#         while True:
#             try:
#                 data = yield from i.__anext__()
#             except StopAsyncIteration:
#                 break
#             else:
#                 if 'id' in data and data['status'] in [
#                     "start", "create",
#                 ]:
#                     data['container'] = yield from containers.get(data['id'])
#
#                 asyncio.async(self.channel.put(data))
#         self.running = False
#
#
# class DockerLog:
#     def __init__(self, docker, container):
#         self.docker = docker
#         self.channel = Channel()
#         self.container = container
#         self.running = False
#
#     def listen(self):
#         return self.channel.listen()
#
#     def saferun(self):
#         if self.running:
#             return
#         self.running = True
#         asyncio.async(self.run())
#
#     @asyncio.coroutine
#     def run(self):
#         self.running = True
#         containers = self.docker.containers
#         response = yield from self.docker._query(
#             'containers/{id}/logs'.format(id=self.container._id),
#             params=dict(
#                 follow=True,
#                 stdout=True,
#                 stderr=True,
#             )
#         )
#
#         for msg in response:
#             msg = yield from msg
#             asyncio.async(self.channel.put(msg))
#
#         yield from response.release()
#
#         self.running = False
