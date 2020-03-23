import asyncio
import sys

import pytest
from async_timeout import timeout

from aiodocker.execs import Stream


async def expect_prompt(stream: Stream) -> str:
    try:
        inp = []
        ret = []
        async with timeout(3):
            while not ret or not ret[-1].endswith(b">>>"):
                msg = await stream.read_out()
                inp.append(msg.data)
                assert msg.stream == 1
                lines = [line.strip() for line in msg.data.splitlines()]
                lines = [line if b"\x1b[K" not in line else b"" for line in lines]
                lines = [line for line in lines if line]
                ret.extend(lines)
            return b"\n".join(ret)
    except asyncio.TimeoutError:
        raise AssertionError(f"[Timeout] {ret} {inp}")


@pytest.mark.asyncio
@pytest.mark.parametrize("stderr", [True, False], ids=lambda x: "stderr={}".format(x))
async def test_exec_attached(shell_container, stderr):
    if stderr:
        cmd = ["python", "-c", "import sys;print('Hello', file=sys.stderr)"]
    else:
        cmd = ["python", "-c", "print('Hello')"]

    execute = await shell_container.exec(
        stdout=True, stderr=True, stdin=True, tty=False, cmd=cmd,
    )
    async with execute.start(detach=False) as stream:
        msg = await stream.read_out()
        assert msg.stream == 2 if stderr else 1
        assert msg.data.strip() == b"Hello"


@pytest.mark.asyncio
@pytest.mark.skipif(
    sys.platform == "win32",
    reason="TTY session in Windows generates too complex ANSI escape sequences",
)
async def test_exec_attached_tty(shell_container):
    execute = await shell_container.exec(
        stdout=True, stderr=True, stdin=True, tty=True, cmd=["python", "-q"],
    )
    async with execute.start(detach=False) as stream:
        await execute.resize(w=80, h=25)

        assert await expect_prompt(stream) == b">>>"

        await stream.write_in(b"import sys\n")
        assert await expect_prompt(stream) == b"import sys\n>>>"

        await stream.write_in(b"print('stdout')\n")
        assert await expect_prompt(stream) == b"print('stdout')\nstdout\n>>>"

        await stream.write_in(b"print('stderr', file=sys.stderr)\n")
        assert (
            await expect_prompt(stream)
            == b"print('stderr', file=sys.stderr)\nstderr\n>>>"
        )

        await stream.write_in(b"exit()\n")


@pytest.mark.asyncio
@pytest.mark.parametrize("tty", [True, False], ids=lambda x: "tty={}".format(x))
@pytest.mark.parametrize("stderr", [True, False], ids=lambda x: "stderr={}".format(x))
async def test_exec_detached(shell_container, tty, stderr):
    if stderr:
        cmd = ["python", "-c", "import sys;print('Hello', file=sys.stderr)"]
    else:
        cmd = ["python", "-c", "print('Hello')"]

    execute = await shell_container.exec(
        stdout=True, stderr=True, stdin=False, tty=tty, cmd=cmd,
    )
    assert await execute.start(detach=True) == b""


@pytest.mark.asyncio
async def test_exec_resize(shell_container):
    execute = await shell_container.exec(
        stdout=True, stderr=True, stdin=True, tty=True, cmd=["python"],
    )
    await execute.start(detach=True)
    await execute.resize(w=120, h=10)


@pytest.mark.asyncio
async def test_exec_inspect(shell_container):
    execute = await shell_container.exec(
        stdout=True,
        stderr=True,
        stdin=False,
        tty=False,
        cmd=["python", "-c", "print('Hello')"],
    )
    data = await execute.inspect()
    assert data["ExitCode"] is None

    ret = await execute.start(detach=True)
    assert ret == b""

    for i in range(100):
        data = await execute.inspect()
        if data["ExitCode"] is None:
            await asyncio.sleep(0.01)
            continue
        assert data["ExitCode"] == 0
        break
    else:
        assert False, "Exec is still running"


@pytest.mark.asyncio
async def test_exec_restore_tty_attached(docker, shell_container):
    exec1 = await shell_container.exec(
        stdout=True, stderr=True, stdin=True, tty=True, cmd=["python"],
    )

    exec2 = docker.containers.exec(exec1.id)
    async with exec2.start() as stream:
        assert exec2._tty
        stream


@pytest.mark.asyncio
async def test_exec_restore_tty_detached(docker, shell_container):
    exec1 = await shell_container.exec(
        stdout=True, stderr=True, stdin=True, tty=True, cmd=["python"],
    )

    exec2 = docker.containers.exec(exec1.id)
    await exec2.start(detach=True)
    assert exec2._tty
