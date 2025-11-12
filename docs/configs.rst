Configs
=======

.. autoclass:: aiodocker.configs.DockerConfigs
    :members:
    :undoc-members:

Example
-------

Create a config
~~~~~~~~~~~~~~~

.. code-block:: python

    import asyncio
    import aiodocker

    async def create_config(docker):
        config = await docker.configs.create(
            name="my_config",
            data="This is my config data",
        )
        return config

    async def create_service(docker, task_template):
        service = await docker.services.create(
            task_template=task_template,
            name="my_service",
        )
        return service

    async def main():
        docker = aiodocker.Docker()
        my_config = await create_config(docker)
        task_template = {
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
                    },
                ],
            },
        }
        service = await create_service(docker, task_template)
        print(service)
        await docker.close()

    if __name__ == "__main__":
        asyncio.run(main())
