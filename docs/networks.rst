==========
Networks
==========

Create a network
==================

.. code-block:: python

    import asyncio
    import aiodocker

    async def create_network():
        docker = aiodocker.Docker()
        network_config = {
            "Name": "isolated_nw",
            "Driver": "bridge",
            "EnableIPv6": False,
            "IPAM": {
                "Driver": "default"
            }
        }
        network = await docker.networks.create(config=network_config)
        print(network)
        await docker.close()

    if __name__ == "__main__":
        asyncio.run(create_network())

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
