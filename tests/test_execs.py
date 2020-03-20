import asyncio

import pytest

from aiodocker.execs import ExecStream


@pytest.mark.asyncio
async def test_exec_attached(shell_container):
    execute = await shell_container.exec(
        stdout=True, stderr=True, stdin=True, tty=True, cmd=["echo", "Hello"],
    )
    async with execute.start(detach=False, tty=True) as resp:
        assert await resp.read_out() == (1, b"Hello\r\n")


@pytest.mark.asyncio
async def test_exec_detached(shell_container):
    execute = await shell_container.exec(
        stdout=True,
        stderr=True,
        stdin=False,
        tty=False,
        cmd=["sh", "-c", "echo Hello"],
    )
    assert await execute.start(detach=True, tty=False) == b""


@pytest.mark.asyncio
@pytest.mark.parametrize("detach", [True, False], ids=lambda x: "detach={}".format(x))
@pytest.mark.parametrize("tty", [True, False], ids=lambda x: "tty={}".format(x))
@pytest.mark.parametrize("stderr", [True, False], ids=lambda x: "stderr={}".format(x))
async def test_exec_start_stream(shell_container, detach, tty, stderr):
    if detach:
        cmd = "echo -n Hello".split()
    else:
        cmd = ["cat"]
    if stderr:
        cmd = ["sh", "-c", " ".join(cmd) + " >&2"]
    execute = await shell_container.exec(
        stdout=True, stderr=True, stdin=True, tty=tty, cmd=cmd
    )
    if detach:
        resp = await execute.start(detach=detach, tty=tty)
        assert isinstance(resp, bytes)
        assert resp == b""
    else:
        async with execute.start(detach=detach, tty=tty) as resp:
            assert isinstance(resp, ExecStream)
            hello = b"Hello"
            await resp.write_in(hello)
            fileno, data = await resp.read_out()
            assert data == hello
            assert fileno == (1 if tty or not stderr else 2)


@pytest.mark.asyncio
async def test_exec_resize(shell_container):
    execute = await shell_container.exec(
        stdout=True, stderr=True, stdin=True, tty=True, cmd=["python"],
    )
    await execute.start(detach=True, tty=True)
    await execute.resize(w=80, h=10)


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

    ret = await execute.start(detach=True, tty=False)
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
