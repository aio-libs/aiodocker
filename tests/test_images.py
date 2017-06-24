import pytest
from io import BytesIO
from aiodocker import utils
from aiodocker.exceptions import DockerError


@pytest.mark.asyncio
async def test_build_from_remote_file(docker):
    remote = ("https://raw.githubusercontent.com/"
              "komljen/dockerfile-examples/master/redis/Dockerfile")
    name = "image:1.0"
    await docker.images.build(tag=name, remote=remote)
    image = await docker.images.get(name)
    assert image


@pytest.mark.asyncio
async def test_history(docker):
    name = "image:1.0"
    history = await docker.images.history(name=name)
    assert history


@pytest.mark.asyncio
async def test_list_images(docker):
    images = await docker.images.list()
    assert images


@pytest.mark.asyncio
async def test_tag_image(docker):
    repository = "registry:5000/image"
    name = "image:1.0"
    await docker.images.tag(name=name, repo=repository, tag="1.0")
    await docker.images.tag(name=name, repo=repository, tag="2.0")
    image = await docker.images.get(name)
    assert len(image['RepoTags']) == 3


@pytest.mark.asyncio
async def test_push_image(docker):
    name = "registry:5000/image"
    await docker.images.push(name=name)


@pytest.mark.asyncio
async def test_delete_image(docker):
    images = await docker.images.list()
    origin_count = len(images)
    image = await docker.images.get("image:1.0")
    tags = image['RepoTags']
    for tag in tags:
        print(tag)
        await docker.images.delete(name=tag)
    images = await docker.images.list()
    assert len(images) == origin_count - 1


@pytest.mark.asyncio
async def test_deleted_image(docker):
    name = "registry:5000/image:1.0"
    with pytest.raises(DockerError) as excinfo:
        await docker.images.get(name=name)
    assert 'no such image:' in str(excinfo.value)


@pytest.mark.asyncio
async def test_pull_image(docker):
    name = "registry:5000/image"
    await docker.images.pull(from_image=name)
    name = "registry:5000/image:1.0"
    image = await docker.images.get(name=name)
    assert image


@pytest.mark.asyncio
async def test_build_from_tar(docker):
    dockerfile = '''
    # Shared Volume
    FROM busybox:buildroot-2014.02
    VOLUME /data
    CMD ["/bin/sh"]
    '''
    f = BytesIO(dockerfile.encode('utf-8'))
    tar_obj = utils.mktar_from_dockerfile(f)
    await docker.images.build(fileobj=tar_obj, encoding="gzip",
                              tag="fromtar/image:1.0")
    tar_obj.close()
    image = await docker.images.get(name="fromtar/image:1.0")
    assert image
