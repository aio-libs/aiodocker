Containers
==========

.. autoclass:: aiodocker.containers.DockerContainers
    :members:
    :undoc-members:

.. autoclass:: aiodocker.containers.DockerContainer
    :members:
    :undoc-members:

Example
-------

Create a container
~~~~~~~~~~~~~~~~~~

.. code-block:: python

    import asyncio
    import aiodocker

    config = {
            "Cmd": ["/bin/ls"],
            "Image": "alpine:latest",
            "AttachStdin": False,
            "AttachStdout": False,
            "AttachStderr": False,
            "Tty": False,
            "OpenStdin": False,
        }

    async def create_container():
        docker = aiodocker.Docker()
        container = await docker.containers.create(config=config)
        print(container)
        await docker.close()

    if __name__ == "__main__":
        asyncio.run(create_container())

.. note::

   Some commonly-used fields — including ``Runtime``, ``Privileged``,
   ``Binds``, ``NetworkMode``, ``RestartPolicy``, and ``PortBindings`` —
   belong **inside** ``HostConfig``, not at the top level of the config
   dict. Docker silently ignores them when placed at the top level. See the
   `Docker Engine API reference
   <https://docs.docker.com/engine/api/latest/#tag/Container/operation/ContainerCreate>`_
   for the authoritative field list. ``aiodocker`` emits a
   :py:class:`UserWarning` when it detects a well-known ``HostConfig``-only
   field at the top level.
