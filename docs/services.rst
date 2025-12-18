Services
========

.. autoclass:: aiodocker.services.DockerServices
    :members:
    :undoc-members:

Example
-------

Create a service
~~~~~~~~~~~~~~~~

.. code-block:: python

    import asyncio
    import aiodocker

    async def create_service():
        docker = aiodocker.Docker()
        task_template = {
            "ContainerSpec": {
                "Image": "redis",
            },
        }
        service = await docker.services.create(
            task_template=task_template,
            name="my_service"
        )
        print(service)
        await docker.close()

    if __name__ == "__main__":
         asyncio.run(create_service())
