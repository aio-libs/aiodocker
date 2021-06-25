============
Secrets
============


Create a secret
========================

.. code-block:: python

   import asyncio
   import aiodocker

   docker = aiodocker.Docker()

   async def create_secret():
       secret = await docker.secrets.create(
           name="my_secret",
           data="you can not read that terrible secret"
       )
       await docker.close()


   if __name__ == '__main__':
       loop = asyncio.get_event_loop()
       loop.run_until_complete(create_secret())
       loop.close()

------------
Reference
------------

DockerSecrets
===============

.. autoclass:: aiodocker.secrets.DockerSecrets
        :members:
        :undoc-members:
