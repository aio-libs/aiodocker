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
