import os
import sys
from io import BytesIO

import pytest

from aiodocker import utils
from aiodocker.exceptions import DockerError


def skip_windows():
    if sys.platform == "win32":
        # replaced xfail with skip for sake of tests speed
        pytest.skip("image operation fails on Windows")


@pytest.mark.asyncio
async def test_build_from_remote_file(docker, random_name, requires_api_version):
    skip_windows()

    requires_api_version(
        "v1.28",
        "TODO: test disabled because it fails on "
        "API version 1.27, this should be fixed",
    )

    remote = (
        "https://raw.githubusercontent.com/aio-libs/"
        "aiodocker/master/tests/docker/Dockerfile"
    )

    tag = "{}:1.0".format(random_name())
    params = {"tag": tag, "remote": remote}
    await docker.images.build(**params)

    image = await docker.images.inspect(tag)
    assert image


@pytest.mark.asyncio
async def test_build_from_remote_tar(docker, random_name):
    skip_windows()

    remote = (
        "https://github.com/aio-libs/aiodocker/"
        "raw/master/tests/docker/docker_context.tar"
    )

    tag = "{}:1.0".format(random_name())
    params = {"tag": tag, "remote": remote}
    await docker.images.build(**params)

    image = await docker.images.inspect(tag)
    assert image


@pytest.mark.asyncio
async def test_history(docker, image_name):
    history = await docker.images.history(name=image_name)
    assert history


@pytest.mark.asyncio
async def test_list_images(docker, image_name):
    images = await docker.images.list(filter=image_name)
    assert len(images) == 1


@pytest.mark.asyncio
async def test_tag_image(docker, random_name, image_name):
    repository = random_name()
    await docker.images.tag(name=image_name, repo=repository, tag="1.0")
    await docker.images.tag(name=image_name, repo=repository, tag="2.0")
    image = await docker.images.inspect(image_name)
    assert len([x for x in image["RepoTags"] if x.startswith(repository)]) == 2


@pytest.mark.asyncio
async def test_push_image(docker, image_name):
    repository = "localhost:5000/image"
    await docker.images.tag(name=image_name, repo=repository)
    await docker.images.push(name=repository)


@pytest.mark.asyncio
async def test_push_image_stream(docker, image_name):
    repository = "localhost:5000/image"
    await docker.images.tag(name=image_name, repo=repository)
    async for item in docker.images.push(name=repository, stream=True):
        pass


@pytest.mark.asyncio
async def test_delete_image(docker, image_name):
    repository = "localhost:5000/image"
    await docker.images.tag(name=image_name, repo=repository)
    assert await docker.images.inspect(repository)
    await docker.images.delete(name=repository)
    images = await docker.images.list(filter=repository)
    assert len(images) == 0


@pytest.mark.asyncio
async def test_not_existing_image(docker, random_name):
    name = "{}:latest".format(random_name())
    with pytest.raises(DockerError) as excinfo:
        await docker.images.inspect(name=name)
    assert excinfo.value.status == 404


@pytest.mark.asyncio
async def test_pull_image(docker, image_name):
    image = await docker.images.inspect(name=image_name)
    assert image

    with pytest.warns(DeprecationWarning):
        image = await docker.images.get(name=image_name)
        assert "Architecture" in image


@pytest.mark.asyncio
async def test_pull_image_stream(docker, image_name):
    image = await docker.images.inspect(name=image_name)
    assert image

    async for item in docker.images.pull(image_name, stream=True):
        pass


@pytest.mark.asyncio
async def test_build_from_tar(docker, random_name, image_name):
    name = "{}:latest".format(random_name())
    dockerfile = f"""
    # Shared Volume
    FROM {image_name}
    """
    f = BytesIO(dockerfile.encode("utf-8"))
    tar_obj = utils.mktar_from_dockerfile(f)
    await docker.images.build(fileobj=tar_obj, encoding="gzip", tag=name)
    tar_obj.close()
    image = await docker.images.inspect(name=name)
    assert image


@pytest.mark.asyncio
async def test_build_from_tar_stream(docker, random_name, image_name):
    name = "{}:latest".format(random_name())
    dockerfile = f"""
    # Shared Volume
    FROM {image_name}
    """
    f = BytesIO(dockerfile.encode("utf-8"))
    tar_obj = utils.mktar_from_dockerfile(f)
    async for item in docker.images.build(
        fileobj=tar_obj, encoding="gzip", tag=name, stream=True
    ):
        pass
    tar_obj.close()
    image = await docker.images.inspect(name=name)
    assert image


@pytest.mark.asyncio
async def test_export_image(docker, image_name):
    name = image_name
    async with docker.images.export_image(name=name) as exported_image:
        assert exported_image
        async for chunk in exported_image.iter_chunks():
            pass


@pytest.mark.asyncio
async def test_import_image(docker):
    skip_windows()

    async def file_sender(file_name=None):
        with open(file_name, "rb") as f:
            chunk = f.read(2 ** 16)
            while chunk:
                yield chunk
                chunk = f.read(2 ** 16)

    dir = os.path.dirname(__file__)
    hello_world = os.path.join(dir, "docker/google-containers-pause.tar")
    response = await docker.images.import_image(data=file_sender(file_name=hello_world))
    for item in response:
        assert "error" not in item

    repository = "gcr.io/google-containers/pause"

    for tag in ["1.0", "go", "latest", "test", "test2"]:
        name = "{}:{}".format(repository, tag)
        image = await docker.images.inspect(name=name)
        assert image


@pytest.mark.asyncio
async def test_pups_image_auth(docker, image_name):
    skip_windows()

    name = image_name
    await docker.images.pull(from_image=name)
    repository = "localhost:5001/image:latest"
    image, tag = repository.rsplit(":", 1)
    registry_addr, image_name = image.split("/", 1)
    await docker.images.tag(name=name, repo=image, tag=tag)

    auth_config = {"username": "testuser", "password": "testpassword"}

    await docker.images.push(name=repository, tag=tag, auth=auth_config)

    await docker.images.delete(name=repository)
    await docker.images.pull(repository, auth={"auth": "dGVzdHVzZXI6dGVzdHBhc3N3b3Jk"})

    await docker.images.inspect(repository)
    await docker.images.delete(name=repository)

    # Now compose_auth_header automatically parse and rebuild
    # the encoded value if required.
    await docker.pull(repository, auth="dGVzdHVzZXI6dGVzdHBhc3N3b3Jk")
    with pytest.raises(ValueError):
        # The repository arg must include the registry address.
        await docker.pull("image:latest", auth={"auth": "dGVzdHVzZXI6dGVzdHBhc3N3b3Jk"})
    await docker.pull(repository, auth={"auth": "dGVzdHVzZXI6dGVzdHBhc3N3b3Jk"})
    await docker.images.inspect(repository)
