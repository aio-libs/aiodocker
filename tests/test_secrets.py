import pytest
import aiodocker


@pytest.mark.asyncio
async def test_list_secrets(swarm):
    data = await swarm.secrets.list()
    assert not data
    secret = await swarm.secrets.create('test_secret', 'test_data')
    data = await swarm.secrets.list()
    assert len(data) == 1
    got = data[0]
    assert got.get('ID', got.get('Id', got.get('id'))) == secret._id


@pytest.mark.asyncio
async def test_create_secret(swarm):
    secret = await swarm.secrets.create('test_secret', 'test_data')
    assert isinstance(secret, aiodocker.secrets.DockerSecret)


@pytest.mark.asyncio
async def test_get_secret(swarm):
    created = await swarm.secrets.create('test_secret', 'test_data')
    secret = await swarm.secrets.get('test_secret')
    assert isinstance(secret, aiodocker.secrets.DockerSecret)
    assert secret._id == created._id


@pytest.mark.asyncio
async def test_secret_work(swarm):
    name = 'test_secret'
    labels = {'test': 'test_label'}
    secret = await swarm.secrets.create(name, 'test_data', labels=labels)
    assert isinstance(secret, aiodocker.secrets.DockerSecret)
    info = await secret.show()
    assert info.get('ID', info.get('Id', info.get('id'))) == secret._id
    assert info.get('Spec').get('Name') == name
    assert info.get('Spec').get('Labels') == labels
    version = info.get('Version').get('Index')
    new_labels = {'test': 'second_label'}
    await secret.update(name, version, labels=new_labels)
    info = await secret.show()
    assert info.get('Spec').get('Name') == name
    assert info.get('Spec').get('Labels') == new_labels


@pytest.mark.asyncio
async def test_secret_delete(swarm):
    secret = await swarm.secrets.create('test_secret', 'test_data')
    data = await swarm.secrets.list()
    assert len(data) == 1
    await secret.delete()
    data = await swarm.secrets.list()
    assert not data
