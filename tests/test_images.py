from __future__ import annotations

import os
import sys
from io import BytesIO
from typing import AsyncIterator, Callable

import pytest

from aiodocker import utils
from aiodocker.docker import Docker
from aiodocker.exceptions import DockerError


def skip_windows() -> None:
    if sys.platform == "win32":
        # replaced xfail with skip for sake of tests speed
        pytest.skip("image operation fails on Windows")


@pytest.mark.asyncio
async def test_build_from_remote_file(
    docker: Docker,
    random_name: Callable[[], str],
    requires_api_version: Callable[[str, str], None],
) -> None:
    skip_windows()

    requires_api_version(
        "v1.28",
        "TODO: test disabled because it fails on "
        "API version 1.27, this should be fixed",
    )

    remote = (
        "https://raw.githubusercontent.com/aio-libs/"
        "aiodocker/main/tests/docker/Dockerfile"
    )

    tag = f"{random_name()}:1.0"
    await docker.images.build(tag=tag, remote=remote, stream=False)

    image = await docker.images.inspect(tag)
    assert image


@pytest.mark.asyncio
async def test_build_from_remote_tar(
    docker: Docker, random_name: Callable[[], str]
) -> None:
    skip_windows()

    remote = (
        "https://github.com/aio-libs/aiodocker/"
        "raw/main/tests/docker/docker_context.tar"
    )

    tag = f"{random_name()}:1.0"
    await docker.images.build(tag=tag, remote=remote, stream=False)

    image = await docker.images.inspect(tag)
    assert image


@pytest.mark.asyncio
async def test_history(docker: Docker, image_name: str) -> None:
    history = await docker.images.history(name=image_name)
    assert history


@pytest.mark.asyncio
async def test_list_images(docker: Docker, image_name: str) -> None:
    images = await docker.images.list(filter=image_name)
    assert len(images) >= 1


@pytest.mark.asyncio
async def test_tag_image(
    docker: Docker, random_name: Callable[[], str], image_name: str
) -> None:
    repository = random_name()
    await docker.images.tag(name=image_name, repo=repository, tag="1.0")
    await docker.images.tag(name=image_name, repo=repository, tag="2.0")
    image = await docker.images.inspect(image_name)
    assert len([x for x in image["RepoTags"] if x.startswith(repository)]) == 2


@pytest.mark.asyncio
async def test_push_image(docker: Docker, image_name: str) -> None:
    repository = "localhost:5000/image"
    await docker.images.tag(name=image_name, repo=repository)
    await docker.images.push(name=repository)


@pytest.mark.asyncio
async def test_push_image_stream(docker: Docker, image_name: str) -> None:
    repository = "localhost:5000/image"
    await docker.images.tag(name=image_name, repo=repository)
    async for item in docker.images.push(name=repository, stream=True):
        pass


@pytest.mark.asyncio
async def test_delete_image(docker: Docker, image_name: str) -> None:
    repository = "localhost:5000/image"
    await docker.images.tag(name=image_name, repo=repository)
    assert await docker.images.inspect(repository)
    await docker.images.delete(name=repository)


@pytest.mark.asyncio
async def test_not_existing_image(
    docker: Docker, random_name: Callable[[], str]
) -> None:
    name = f"{random_name()}:latest"
    with pytest.raises(DockerError) as excinfo:
        await docker.images.inspect(name=name)
    assert excinfo.value.status == 404


@pytest.mark.asyncio
async def test_pull_image(docker: Docker, image_name: str) -> None:
    image = await docker.images.inspect(name=image_name)
    assert image

    with pytest.warns(DeprecationWarning):
        image = await docker.images.get(name=image_name)
        assert "Architecture" in image


@pytest.mark.asyncio
async def test_pull_image_stream(docker: Docker, image_name: str) -> None:
    image = await docker.images.inspect(name=image_name)
    assert image

    async for item in docker.images.pull(image_name, stream=True):
        pass


@pytest.mark.asyncio
async def test_build_from_tar(
    docker: Docker, random_name: Callable[[], str], image_name: str
) -> None:
    name = f"{random_name()}:latest"
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
async def test_build_from_tar_stream(
    docker: Docker, random_name: Callable[[], str], image_name: str
) -> None:
    name = f"{random_name()}:latest"
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
async def test_export_image(docker: Docker, image_name: str) -> None:
    name = image_name
    async with docker.images.export_image(name=name) as exported_image:
        assert exported_image
        async for chunk in exported_image.iter_chunks():
            pass


@pytest.mark.asyncio
async def test_import_image(docker: Docker) -> None:
    skip_windows()

    async def file_sender(file_name: str) -> AsyncIterator[bytes]:
        with open(file_name, "rb") as f:
            chunk = f.read(2**16)
            while chunk:
                yield chunk
                chunk = f.read(2**16)

    dir = os.path.dirname(__file__)
    hello_world = os.path.join(dir, "docker/google-containers-pause.tar")
    # FIXME: improve annotation for chunked data generator
    response = await docker.images.import_image(data=file_sender(hello_world))  # type: ignore
    for item in response:
        assert "error" not in item

    repository = "gcr.io/google-containers/pause"

    for tag in ["1.0", "go", "latest", "test", "test2"]:
        name = f"{repository}:{tag}"
        image = await docker.images.inspect(name=name)
        assert image


@pytest.mark.asyncio
async def test_pups_image_auth(docker: Docker, image_name: str) -> None:
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


@pytest.mark.asyncio
async def test_build_image_invalid_platform(docker: Docker, image_name: str) -> None:
    dockerfile = f"""
        FROM {image_name}
        """
    f = BytesIO(dockerfile.encode("utf-8"))
    tar_obj = utils.mktar_from_dockerfile(f)
    with pytest.raises(DockerError) as excinfo:
        async for item in docker.images.build(
            fileobj=tar_obj, encoding="gzip", stream=True, platform="foo"
        ):
            pass
    tar_obj.close()
    assert excinfo.value.status == 400
    assert (
        "unknown operating system or architecture: invalid argument"
        in excinfo.exconly()
    )


@pytest.mark.asyncio
async def test_pull_image_invalid_platform(docker: Docker, image_name: str) -> None:
    with pytest.raises(DockerError) as excinfo:
        await docker.images.pull("hello-world", platform="foo")

    assert excinfo.value.status == 400
    assert (
        "unknown operating system or architecture: invalid argument"
        in excinfo.exconly()
    )
