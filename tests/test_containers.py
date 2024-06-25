import asyncio
import sys

import pytest

from aiodocker.containers import DockerContainer
from aiodocker.docker import Docker
from aiodocker.exceptions import DockerContainerError, DockerError


async def _validate_hello(container: DockerContainer) -> None:
    try:
        await container.start()
        response = await container.wait()
        assert response["StatusCode"] == 0
        await asyncio.sleep(5)  # wait for output in case of slow test container
        logs = await container.log(stdout=True)
        assert "hello\n" in logs

        with pytest.raises(TypeError):
            await container.log()
    finally:
        await container.delete(force=True)


@pytest.mark.asyncio
async def test_run_existing_container(docker: Docker, image_name: str) -> None:
    await docker.pull(image_name)
    container = await docker.containers.run(
        config={
            "Cmd": ["-c", "print('hello')"],
            "Entrypoint": "python",
            "Image": image_name,
        }
    )

    await _validate_hello(container)


@pytest.mark.asyncio
async def test_run_container_with_missing_image(
    docker: Docker, image_name: str
) -> None:
    try:
        await docker.images.delete(image_name)
    except DockerError as e:
        if e.status == 404:
            pass  # already missing, pass
        elif e.status == 409:
            await docker.images.delete(image_name, force=True)
        else:
            raise

    # should automatically pull the image
    container = await docker.containers.run(
        config={
            "Cmd": ["-c", "print('hello')"],
            "Entrypoint": "python",
            "Image": image_name,
        }
    )

    await _validate_hello(container)


@pytest.mark.asyncio
async def test_run_failing_start_container(docker: Docker, image_name: str) -> None:
    try:
        await docker.images.delete(image_name)
    except DockerError as e:
        if e.status == 404:
            pass  # already missing, pass
        elif e.status == 409:
            await docker.images.delete(image_name, force=True)
        else:
            raise

    with pytest.raises(DockerContainerError) as e_info:
        await docker.containers.run(
            config={
                # we want to raise an error
                # `executable file not found`
                "Cmd": ["pytohon", "-c" "print('hello')"],
                "Image": image_name,
            }
        )

    assert e_info.value.container_id
    # This container is created but not started!
    # We should delete it afterwards.
    cid = e_info.value.container_id
    container = docker.containers.container(cid)
    await container.delete()


@pytest.mark.asyncio
async def test_restart(docker: Docker, image_name: str) -> None:
    # sleep for 10 min to emulate hanging container
    container = await docker.containers.run(
        config={
            "Cmd": ["python", "-c", "import time;time.sleep(600)"],
            "Image": image_name,
        }
    )
    try:
        details = await container.show()
        assert details["State"]["Running"]
        startTime = details["State"]["StartedAt"]
        await container.restart(timeout=1)
        await asyncio.sleep(3)
        details = await container.show()
        assert details["State"]["Running"]
        restartTime = details["State"]["StartedAt"]

        assert restartTime > startTime

        await container.stop()
    finally:
        await container.delete(force=True)


@pytest.mark.asyncio
async def test_container_stats_list(docker: Docker, image_name: str) -> None:
    container = await docker.containers.run(
        config={
            "Cmd": ["-c", "print('hello')"],
            "Entrypoint": "python",
            "Image": image_name,
        }
    )

    try:
        await container.start()
        response = await container.wait()
        assert response["StatusCode"] == 0
        stats = await container.stats(stream=False)
        assert "cpu_stats" in stats[0]
    finally:
        await container.delete(force=True)


@pytest.mark.asyncio
async def test_container_stats_stream(docker: Docker, image_name: str) -> None:
    container = await docker.containers.run(
        config={
            "Cmd": ["-c", "print('hello')"],
            "Entrypoint": "python",
            "Image": image_name,
        }
    )

    try:
        await container.start()
        response = await container.wait()
        assert response["StatusCode"] == 0
        count = 0
        async for stat in container.stats():
            assert "cpu_stats" in stat
            count += 1
            if count > 3:
                break
    finally:
        await container.delete(force=True)


@pytest.mark.asyncio
async def test_resize(shell_container: DockerContainer) -> None:
    await shell_container.resize(w=120, h=10)


@pytest.mark.skipif(
    sys.platform == "win32", reason="Commit unpaused containers doesn't work on Windows"
)
@pytest.mark.asyncio
async def test_commit(
    docker: Docker, image_name: str, shell_container: DockerContainer
) -> None:
    """
    "Container" key was removed in v1.45.
    "ContainerConfig" is not present, although this information is now present in "Config"
    These changes have been verified against v1.45.
    """
    ret = await shell_container.commit()
    img_id = ret["Id"]
    img = await docker.images.inspect(img_id)

    assert "Image" in img["Config"]
    assert image_name == img["Config"]["Image"]
    python_img = await docker.images.inspect(image_name)
    python_id = python_img["Id"]
    assert "Parent" in img
    assert img["Parent"] == python_id
    await docker.images.delete(img_id)


@pytest.mark.skipif(
    sys.platform == "win32", reason="Commit unpaused containers doesn't work on Windows"
)
@pytest.mark.asyncio
async def test_commit_with_changes(
    docker: Docker, image_name: str, shell_container: DockerContainer
) -> None:
    ret = await shell_container.commit(changes=["EXPOSE 8000", 'CMD ["py"]'])
    img_id = ret["Id"]
    img = await docker.images.inspect(img_id)
    assert "8000/tcp" in img["Config"]["ExposedPorts"]
    assert img["Config"]["Cmd"] == ["py"]
    await docker.images.delete(img_id)


@pytest.mark.skipif(sys.platform == "win32", reason="Pause doesn't work on Windows")
@pytest.mark.asyncio
async def test_pause_unpause(shell_container: DockerContainer) -> None:
    await shell_container.pause()
    container_info = await shell_container.show()
    assert "State" in container_info
    state = container_info["State"]
    assert "ExitCode" in state
    assert state["ExitCode"] == 0
    assert "Running" in state
    assert state["Running"] is True
    assert "Paused" in state
    assert state["Paused"] is True

    await shell_container.unpause()
    container_info = await shell_container.show()
    assert "State" in container_info
    state = container_info["State"]
    assert "ExitCode" in state
    assert state["ExitCode"] == 0
    assert "Running" in state
    assert state["Running"] is True
    assert "Paused" in state
    assert state["Paused"] is False


@pytest.mark.asyncio
async def test_capture_log_oneshot(docker: Docker, image_name: str) -> None:
    container = await docker.containers.run(
        config={
            "Cmd": [
                "python",
                "-c",
                "import time;time.sleep(0.2);print(1);time.sleep(0.2);print(2)",
            ],
            "Image": image_name,
        }
    )
    try:
        await asyncio.sleep(1)
        log = await container.log(
            stdout=True,
            stderr=True,
            follow=False,
        )
        assert ["1\n", "2\n"] == log
    finally:
        await container.delete(force=True)


@pytest.mark.asyncio
async def test_capture_log_stream(docker: Docker, image_name: str) -> None:
    container = await docker.containers.run(
        config={
            "Cmd": [
                "python",
                "-c",
                "import time;time.sleep(0.2);print(1);time.sleep(0.2);print(2)",
            ],
            "Image": image_name,
        }
    )
    try:
        log_gen = container.log(
            stdout=True,
            stderr=True,
            follow=True,
        )
        log = []
        async for line in log_gen:
            log.append(line)
        assert ["1\n", "2\n"] == log
    finally:
        await container.delete(force=True)


@pytest.mark.asyncio
async def test_cancel_log(docker: Docker) -> None:
    container = docker.containers.container("invalid_container_id")

    with pytest.raises(DockerError):
        await container.log(
            stdout=True,
            stderr=True,
        )
