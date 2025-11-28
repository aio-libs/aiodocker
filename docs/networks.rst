Networks
========

.. autoclass:: aiodocker.networks.DockerNetworks
    :members:
    :undoc-members:

.. autoclass:: aiodocker.networks.DockerNetwork
    :members:
    :undoc-members:

Example
-------

Create a network
~~~~~~~~~~~~~~~~

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
