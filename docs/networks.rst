==========
Networks
==========

Create a network
==================

.. code-block:: python

    import asyncio
    import aiodocker

    docker = aiodocker.Docker()

    config = {
        "Name": "isolated_nw",
        "Driver": "bridge",
        "EnableIPv6": False,
        "IPAM": {
            "Driver": "default"
        }
    }

    async def create_network():
        network = await docker.networks.create(config=config)
        print(network)
        await docker.close()


    if __name__ == '__main__':
        loop = asyncio.get_event_loop()
        loop.run_until_complete(create_network())
        loop.close()

---------
Reference
---------

DockerNetworks
================
.. autoclass:: aiodocker.docker.DockerNetworks
        :members:
        :undoc-members:

DockerNetwork
===============
.. autoclass:: aiodocker.docker.DockerNetwork
        :members:
        :undoc-members:
