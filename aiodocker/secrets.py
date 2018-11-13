import json
import base64

from .utils import clean_filters


class DockerSecrets:
    def __init__(self, docker):
        self.docker = docker

    async def list(self, filters=None):
        """
        List all secrets

        Args:
            filters: a dict with a list of filters
        Returns:
            a list with dict info about each secret
        """
        params = {"filters": clean_filters(filters)}
        url = "secrets"
        data = await self.docker._query_json(url, params=params)
        return data

    async def create(self, name, value, labels=None, driver=None):
        """
        Create a secret

        Args:
            name: secret's name
            value: secret's value
            labels: dict with labels
            driver: dict with driver

        Returns:
            DockerSecret instance
        """
        if not isinstance(value, bytes):
            value = value.encode('utf-8')
        data = base64.urlsafe_b64encode(value)
        data = data.decode('utf-8')
        config = {
            'Data': data,
            'Name': name,
            'Labels': labels
        }
        if driver is not None:
            config['Driver'] = driver

        url = "secrets/create"
        config = json.dumps(config, sort_keys=True).encode('utf-8')
        data = await self.docker._query_json(
            url,
            method="POST",
            data=config,
        )
        data_id = data.get('ID', data.get('Id', data.get('id')))
        return DockerSecret(self.docker, id_=data_id)

    async def get(self, name):
        """
        Get a secret by name

        Args:
            name: secret's name

        Returns:
            DockerSecret instance
        """
        secrets = await self.list(filters={'name': name})
        for secret in secrets:
            if not name == secret.get('Spec', {}).get('Name'):
                continue
            data_id = secret.get('ID', secret.get('Id', secret.get('id')))
            return DockerSecret(self.docker, id_=data_id)


class DockerSecret:
    def __init__(self, docker, id_):
        self.docker = docker
        self._id = id_

    async def show(self):
        """
        Inspect a secret

        Returns:
            a dict with info about a secret
        """

        url = "secrets/{self._id}".format(self=self)
        data = await self.docker._query_json(url)
        return data

    async def delete(self):
        """
        Delete a secret
        """

        url = "secrets/{self._id}".format(self=self)
        response = await self.docker._query(
            url,
            method="DELETE",
        )
        await response.release()
        return

    async def update(self, name, version, labels=None):
        """
        Update a secret.
        Currently, only the Labels field can be updated.
        All other fields must remain unchanged
        from the SecretInspect endpoint response values.

        Args:
            name:    secret's name
            version: The version number of the object such as node, etc.
                     This is needed to avoid conflicting writes.
                     Get it via secret.show().get('Version').get('Index')
            labels:  dict with labels

        Returns:
            True if successful.
        """

        data = {
            'Name': name,
            'Labels': labels
        }
        url = "secrets/{self._id}/update".format(self=self)
        await self.docker._query_json(
            url,
            method="POST",
            data=data,
            params={"version": version}
        )
        return True
