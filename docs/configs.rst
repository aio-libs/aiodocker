============
Configs
============


Create a config
========================

.. code-block:: python

    import asyncio
    import aiodocker

    docker = aiodocker.Docker()

    async def create_config():
        config = await docker.configs.create(
            name="my_config",
            data="This is my config data"
        )
        await docker.close()
        return config

    async def create_service(TaskTemplate):
        service = await docker.services.create(
            task_template=TaskTemplate,
            name="my_service"
        )
        await docker.close()

    if __name__ == '__main__':
        loop = asyncio.get_event_loop()
        my_config = loop.run_until_complete(create_config())
        TaskTemplate = {
            "ContainerSpec": {
                "Image": "redis",
                "Configs": [
                {
                    "File": {
                        "Name": my_config["Spec"]["Name"],
                        "UID": "0",
                        "GID": "0",
                        "Mode": 292
                    },
                    "ConfigID": my_config["ID"],
                    "ConfigName": my_config["Spec"]["Name"],
                }
                ],
            },
        }
        loop.run_until_complete(create_service(TaskTemplate))
        loop.close()


------------
Reference
------------

DockerConfigs
===============

.. autoclass:: aiodocker.configs.DockerConfigs
        :members:
        :undoc-members:
