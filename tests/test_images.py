import uuid
from io import BytesIO

import pytest
from aiodocker import utils
from aiodocker.exceptions import DockerError


def _random_name():
    return "aiodocker-" + uuid.uuid4().hex[:7]


@pytest.mark.asyncio
async def test_build_from_remote_file(docker):
    remote = ("https://raw.githubusercontent.com/aio-libs/"
              "aiodocker/master/tests/docker/Dockerfile")

    tag = "{}:1.0".format(_random_name())
    params = {'tag': tag, 'remote': remote}
    await docker.images.build(**params)

    image = await docker.images.get(tag)
    assert image


@pytest.mark.asyncio
async def test_build_from_remote_tar(docker):
    remote = ("https://github.com/aio-libs/aiodocker/"
              "raw/master/tests/docker/docker_context.tar")

    tag = "{}:1.0".format(_random_name())
    params = {'tag': tag, 'remote': remote}
    await docker.images.build(**params)

    image = await docker.images.get(tag)
    assert image


@pytest.mark.asyncio
async def test_history(docker):
    name = "busybox:latest"
    history = await docker.images.history(name=name)
    assert history


@pytest.mark.asyncio
async def test_list_images(docker):
    name = "busybox:latest"
    images = await docker.images.list(filter=name)
    assert len(images) == 1


@pytest.mark.asyncio
async def test_tag_image(docker):
    name = "busybox:latest"
    repository = _random_name()
    await docker.images.tag(name=name, repo=repository, tag="1.0")
    await docker.images.tag(name=name, repo=repository, tag="2.0")
    image = await docker.images.get(name)
    assert len([x for x in image['RepoTags'] if x.startswith(repository)]) == 2


@pytest.mark.asyncio
async def test_push_image(docker):
    name = "busybox:latest"
    repository = "localhost:5000/image"
    await docker.images.tag(name=name, repo=repository)
    await docker.images.push(name=repository)


@pytest.mark.asyncio
async def test_delete_image(docker):
    name = "busybox:latest"
    repository = "localhost:5000/image"
    await docker.images.tag(name=name, repo=repository)
    assert await docker.images.get(repository)
    await docker.images.delete(name=repository)
    images = await docker.images.list(filter=repository)
    assert len(images) == 0


@pytest.mark.asyncio
async def test_not_existing_image(docker):
    name = "{}:latest".format(_random_name())
    with pytest.raises(DockerError) as excinfo:
        await docker.images.get(name=name)
    assert excinfo.value.status == 404


@pytest.mark.asyncio
async def test_pull_image(docker):
    name = "busybox:latest"
    image = await docker.images.get(name=name)
    assert image


@pytest.mark.asyncio
async def test_build_from_tar(docker):
    name = "{}:latest".format(_random_name())
    dockerfile = '''
    # Shared Volume
    FROM busybox:buildroot-2014.02
    VOLUME /data
    CMD ["/bin/sh"]
    '''
    f = BytesIO(dockerfile.encode('utf-8'))
    tar_obj = utils.mktar_from_dockerfile(f)
    await docker.images.build(fileobj=tar_obj, encoding="gzip", tag=name)
    tar_obj.close()
    image = await docker.images.get(name=name)
    assert image
