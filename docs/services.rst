============
Services
============


Create a service
========================

.. code-block:: python

   import asyncio
   import aiodocker

   docker = aiodocker.Docker()

   TaskTemplate = {
       "ContainerSpec": {
           "Image": "redis",
           },
    }

    async def create_service():
        service = await docker.services.create(
                            task_template=TaskTemplate,
                            name="my_service"
                            )
        await docker.close()


   if __name__ == '__main__':
       loop = asyncio.get_event_loop()
       loop.run_until_complete(create_service())
       loop.close()

------------
Reference
------------

DockerServices
===============

.. autoclass:: aiodocker.services.DockerServices
        :members:
        :undoc-members:
