import pytest


@pytest.mark.asyncio
async def test_exec_start_stream(shell_container):
    execute = await shell_container.exec_create(
        AttachStdout=True, AttachStderr=True,
        AttachStdin=True, Tty=True,
        Cmd=['cat'],
    )
    stream = await execute.start(stream=True, Detach=False, Tty=True)
    await stream.send_str("Hello")
    msg = await stream.receive()
    assert msg.data == b'Hello'


@pytest.mark.asyncio
async def test_exec_resize(shell_container):
    execute = await shell_container.exec_create(
        AttachStdout=True, AttachStderr=True,
        AttachStdin=True, Tty=True,
        Cmd=['/bin/ash'],
    )
    await execute.start(stream=True, Detach=False, Tty=True)
    await execute.resize(h=10, w=80)


@pytest.mark.asyncio
async def test_exec_inspect(shell_container):
    execute = await shell_container.exec_create(
        AttachStdout=True, AttachStderr=True,
        AttachStdin=True, Tty=True,
        Cmd=['echo', 'Hello'],
    )
    await execute.start(Detach=False, Tty=True)
    data = await execute.inspect()
    assert data['ExitCode'] == 0
