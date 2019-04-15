import pytest

from aiohttp import WSMsgType, ClientWebSocketResponse
from aiodocker.execute import STDOUT, STDERR


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
    execute = await shell_container.exec_create(
        AttachStdout=True, AttachStderr=True, AttachStdin=True, Tty=tty, Cmd=cmd
    )
    resp = await execute.start(Detach=detach, Tty=tty)
    if detach:
        assert isinstance(resp, bytes)
        assert resp == b""
    else:
        assert isinstance(resp, ClientWebSocketResponse)
        hello = b"Hello"
        await resp.send_bytes(hello)
        msg = await resp.receive()
        assert msg.data == hello
        # We can't use sys.stdout.fileno() and sys.stderr.fileno() in the test because
        # pytest changes that so it can capture output.
        assert msg.extra == (STDOUT if tty or not stderr else STDERR)


@pytest.mark.asyncio
async def test_exec_resize(shell_container):
    execute = await shell_container.exec_create(
        AttachStdout=True,
        AttachStderr=True,
        AttachStdin=True,
        Tty=True,
        Cmd=["/bin/ash"],
    )
    await execute.start(Detach=False, Tty=True)
    await execute.resize(h=10, w=80)


@pytest.mark.asyncio
async def test_exec_inspect(shell_container):
    execute = await shell_container.exec_create(
        AttachStdout=True,
        AttachStderr=True,
        AttachStdin=True,
        Tty=True,
        Cmd=["echo", "Hello"],
    )
    resp = await execute.start(Detach=False, Tty=True)
    assert (await resp.receive()).data == b"Hello\r\n"
    assert (await resp.receive()).type == WSMsgType.CLOSED
    assert resp.closed
    data = await execute.inspect()
    assert data["ExitCode"] == 0
