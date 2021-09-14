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
        return secret

    async def create_service(TaskTemplate):
        service = await docker.services.create(
            task_template=TaskTemplate,
            name="my_service"
        )
        await docker.close()

    if __name__ == '__main__':
        loop = asyncio.get_event_loop()
        my_secret = loop.run_until_complete(create_secret())
        TaskTemplate = {
            "ContainerSpec": {
                "Image": "redis",
                "Secrets": [
                {
                    "File": {
                        "Name": my_secret["Spec"]["Name"],
                        "UID": "0",
                        "GID": "0",
                        "Mode": 292
                    },
                    "SecretID": my_secret["ID"],
                    "SecretName": my_secret["Spec"]["Name"]
                }
                ],
            },
        }
        loop.run_until_complete(create_service(TaskTemplate))
        loop.close()


------------
Reference
------------

DockerSecrets
===============

.. autoclass:: aiodocker.secrets.DockerSecrets
        :members:
        :undoc-members:
