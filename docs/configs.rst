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
       service = await docker.configs.create(
           name="my_config",
           data="This is my config data"
       )
       await docker.close()


   if __name__ == '__main__':
       loop = asyncio.get_event_loop()
       loop.run_until_complete(create_config())
       loop.close()

------------
Reference
------------

DockerConfigs
===============

.. autoclass:: aiodocker.configs.DockerConfigs
        :members:
        :undoc-members:
