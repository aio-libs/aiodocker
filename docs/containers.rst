==========
Containers
==========

Create a container
==================

.. code-block:: python

   import asyncio
   import aiodocker

   docker = aiodocker.Docker()

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
       container = await docker.containers.create(config=config)
       print(container)
       await docker.close()


   if __name__ == '__main__':
       loop = asyncio.get_event_loop()
       loop.run_until_complete(create_container())
       loop.close()

---------
Reference
---------

DockerContainers
================
.. autoclass:: aiodocker.docker.DockerContainers
        :members:
        :undoc-members:

DockerContainer
===============
.. autoclass:: aiodocker.docker.DockerContainer
        :members:
        :undoc-members:
