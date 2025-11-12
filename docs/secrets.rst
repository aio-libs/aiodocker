Secrets
=======

.. autoclass:: aiodocker.secrets.DockerSecrets
    :members:
    :undoc-members:

Example
-------

Create a secret
~~~~~~~~~~~~~~~

.. code-block:: python

    import asyncio
    import aiodocker

    async def create_secret(docker):
        secret = await docker.secrets.create(
            name="my_secret",
            data="you can not read that terrible secret"
        )
        return secret

    async def create_service(docker, task_template):
        service = await docker.services.create(
            task_template=task_template,
            name="my_service"
        )
        return service

    async def main():
        docker = aiodocker.Docker()
        my_secret = await create_secret(docker)
        task_template = {
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
                    },
                ],
            },
        }
        service = await create_service(docker, task_template)
        print(service)
        await docker.close()

    if __name__ == "__main__":
        asyncio.run(main())
