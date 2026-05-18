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

List containers
~~~~~~~~~~~~~~~

By default, ``list()`` only returns running containers (equivalent to
``docker ps``). To include stopped containers (equivalent to ``docker ps -a``),
pass ``all=True``:

.. code-block:: python

    import asyncio
    import aiodocker

    async def list_containers():
        docker = aiodocker.Docker()
        # Running containers only
        running = await docker.containers.list()
        # All containers, including stopped ones
        all_containers = await docker.containers.list(all=True)
        for c in all_containers:
            print(c["Id"], c["State"])
        await docker.close()

    if __name__ == "__main__":
        asyncio.run(list_containers())

Any keyword argument is forwarded as a query parameter to the Docker Engine
``GET /containers/json`` endpoint, so ``filters``, ``limit``, and ``size`` work
the same way — see the `Docker Engine API reference
<https://docs.docker.com/reference/api/engine/latest/#tag/Container/operation/ContainerList>`_.

Bind-mount a host directory
~~~~~~~~~~~~~~~~~~~~~~~~~~~

``containers.create()`` forwards its ``config`` dict to the Docker Engine
`POST /containers/create
<https://docs.docker.com/reference/api/engine/latest/#tag/Container/operation/ContainerCreate>`_
endpoint, so any ``HostConfig`` field is available. Two ways to bind-mount a
host path:

**Legacy** — ``HostConfig.Binds`` takes ``"<host>:<container>[:<opts>]"`` strings.
Options are comma-separated and include ``ro``, ``rw``, ``z``/``Z`` (SELinux
relabel), and the propagation modes ``shared`` / ``rshared`` / ``slave`` /
``rslave`` / ``private`` / ``rprivate``:

.. code-block:: python

    config = {
        "Image": "alpine:latest",
        "Cmd": ["/bin/ls", "/data"],
        "HostConfig": {
            "Binds": ["/host/path:/data:ro,shared"],
        },
    }

**Recommended** — ``HostConfig.Mounts`` is a list of structured mount specs.
Propagation is a named field, which is easier to read and harder to mistype:

.. code-block:: python

    config = {
        "Image": "alpine:latest",
        "Cmd": ["/bin/ls", "/data"],
        "HostConfig": {
            "Mounts": [
                {
                    "Type": "bind",
                    "Source": "/host/path",
                    "Target": "/data",
                    "ReadOnly": True,
                    "BindOptions": {"Propagation": "shared"},
                },
            ],
        },
    }

.. note::

   Propagation modes other than ``rprivate`` require the **host-side** mount
   to already have a compatible propagation type — e.g. ``shared`` only works
   if ``/host/path`` is itself a shared mount on the host (see
   ``findmnt -o TARGET,PROPAGATION`` and ``mount --make-shared``). This is a
   Linux kernel constraint, not an aiodocker limitation; if the host mount is
   private, Docker will silently downgrade or reject the propagation flag.
