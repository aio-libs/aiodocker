=======
Secrets
=======

Create secret
=============

.. code-block:: python

   import asyncio
   import aiodocker

   docker = aiodocker.Docker()

   async def create_secret(name, value):
       secret = await docker.secrets.create(name, value)
       print(secret)
       await docker.close()


   if __name__ == '__main__':
       loop = asyncio.get_event_loop()
       loop.run_until_complete(create_container('my_name', 'data'))
       loop.close()

----------
Reference
----------

DockerSecrets
=============

.. autoclass:: aiodocker.secrets.DockerSecrets
        :members:
        :undoc-members:

DockerSecret
==============

.. autoclass:: aiodocker.secrets.DockerSecret
        :members:
        :undoc-members:
