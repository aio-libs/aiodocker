from io import BytesIO

import pytest
from aiodocker import utils
from aiodocker.errors import ImageNotFound


@pytest.mark.asyncio
async def test_build_from_remote_file(docker, random_name):
    remote = ("https://raw.githubusercontent.com/aio-libs/"
              "aiodocker/master/tests/docker/Dockerfile")

    tag = "{}:1.0".format(random_name())
    params = {
        'tag': tag,
        'remote': remote
    }
    await docker.images.build(**params)

    image = await docker.images.get(tag)
    assert image


@pytest.mark.asyncio
async def test_build_from_remote_tar(docker, random_name):
    remote = ("https://github.com/aio-libs/aiodocker/"
              "raw/master/tests/docker/docker_context.tar")

    tag = "{}:1.0".format(random_name())
    params = {
        'tag': tag,
        'remote': remote
    }
    await docker.images.build(**params)

    image = await docker.images.get(tag)
    assert image


@pytest.mark.asyncio
async def test_history(docker):
    name = "alpine:latest"
    image = await docker.images.get(name)
    history = await image.history()
    assert history


@pytest.mark.asyncio
async def test_list_images(docker):
    name = "alpine:latest"
    images = await docker.images.list(name=name)
    assert len(images) == 1


@pytest.mark.asyncio
async def test_tag_image(docker, random_name):
    name = "alpine:latest"
    image = await docker.images.get(name)
    repository = random_name()
    await image.tag(repository=repository, tag="1.0")
    await image.tag(repository=repository, tag="2.0")
    image = await docker.images.get(name)
    assert len([x for x in image.tags if x.startswith(repository)]) == 2


@pytest.mark.asyncio
async def test_push_image(docker):
    name = "alpine:latest"
    repository = "localhost:5000/image"
    image = await docker.images.get(name)
    await image.tag(repository=repository)
    await docker.images.push(repository=repository)


@pytest.mark.asyncio
async def test_delete_image(docker):
    name = "alpine:latest"
    repository = "localhost:5000/image"
    image = await docker.images.get(name)
    await image.tag(repository=repository)
    assert await docker.images.get(repository)
    await docker.images.remove(name=repository)
    images = await docker.images.list(name=repository)
    assert len(images) == 0


@pytest.mark.asyncio
async def test_not_existing_image(docker, random_name):
    name = "{}:latest".format(random_name())
    with pytest.raises(ImageNotFound) as excinfo:
        await docker.images.get(name=name)
    assert isinstance(excinfo.value, ImageNotFound)


@pytest.mark.asyncio
async def test_pull_image(docker):
    name = "alpine:latest"
    image = await docker.images.get(name=name)
    assert image


@pytest.mark.asyncio
async def test_build_from_tar(docker, random_name):
    name = "{}:latest".format(random_name())
    dockerfile = '''
    # Shared Volume
    FROM alpine:latest
    VOLUME /data
    CMD ["/bin/sh"]
    '''
    f = BytesIO(dockerfile.encode('utf-8'))
    tar_obj = utils.mktar_from_dockerfile(f)
    await docker.images.build(fileobj=tar_obj, encoding="gzip", tag=name)
    tar_obj.close()
    image = await docker.images.get(name=name)
    assert image


@pytest.mark.asyncio
async def test_pups_image_auth(docker):
    name = "alpine:latest"
    await docker.images.pull(name)
    image_obj = await docker.images.get(name=name)
    repository = "localhost:5001/image:latest"
    image, tag = repository.rsplit(':', 1)
    await image_obj.tag(repository=image, tag=tag)

    auth_config = {
        'username': "testuser",
        'password': "testpassword"
    }

    await docker.images.push(repository=repository, tag=tag, auth_config=auth_config)

    await docker.images.remove(name=repository)
    await docker.images.pull(repository,
                             auth_config={
                                 "auth": "dGVzdHVzZXI6dGVzdHBhc3N3b3Jk"
                             })

    await docker.images.get(repository)
    await docker.images.remove(name=repository)

    # Now compose_auth_header automatically parse and rebuild
    # the encoded value if required.
    await docker.images.pull(repository,
                             auth_config="dGVzdHVzZXI6dGVzdHBhc3N3b3Jk")
    with pytest.raises(ValueError):
        # The repository arg must include the registry address.
        await docker.images.pull("image:latest",
                                 auth_config={
                                     "auth": "dGVzdHVzZXI6dGVzdHBhc3N3b3Jk"
                                 })
    await docker.images.pull(repository,
                             auth_config={
                                 "auth": "dGVzdHVzZXI6dGVzdHBhc3N3b3Jk"
                             })
    await docker.images.get(repository)
