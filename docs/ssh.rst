================
SSH Connections
================

aiodocker supports connecting to remote Docker hosts over SSH using the ``ssh://`` URL scheme. This feature requires the ``asyncssh`` library and follows the same security principles as docker-py.

The SSH connector uses ``docker system dial-stdio`` to communicate with the remote Docker daemon, which automatically discovers and uses the correct socket path on the remote host. This works seamlessly with standard Docker installations, rootless Docker, and custom socket configurations without requiring manual socket path specification.

Installation
============

Install aiodocker with SSH support:

.. code-block:: bash

   pip install aiodocker[ssh]

Basic Usage
===========

Connect to a remote Docker host using an SSH URL:

.. code-block:: python

    import asyncio
    import aiodocker

    async def main():
        # Connect to Docker over SSH
        async with aiodocker.Docker(url="ssh://user@remote-host:22") as docker:
            # Use Docker API normally
            version = await docker.version()
            print(f"Docker version: {version['Version']}")

            # List containers
            containers = await docker.containers.list()
            for container in containers:
                print(f"Container: {container['Names'][0]}")

    if __name__ == "__main__":
        asyncio.run(main())

URL Format
==========

SSH URLs follow this format::

    ssh://[user[:password]@]host[:port]

Examples:

* ``ssh://ubuntu@host:22`` - Connect to host on port 22
* ``ssh://ubuntu@host`` - Connect using default SSH port (22)
* ``ssh://dockeruser@production.example.com:2222`` - Custom port

**Note on Socket Paths:**

Unlike traditional SSH port forwarding approaches, aiodocker uses ``docker system dial-stdio`` which automatically discovers the correct Docker socket on the remote host. Socket paths in URLs (e.g., ``ssh://user@host///var/run/docker.sock``) are accepted for backward compatibility but are ignored.

This automatic discovery means the connector works correctly with:

* Standard Docker installations (``/var/run/docker.sock``)
* Rootless Docker (``/run/user/1000/docker.sock``)
* Custom socket paths configured in the remote Docker daemon
* Docker contexts on the remote host

Authentication
==============

SSH Key Authentication (Recommended)
-------------------------------------

The preferred method is SSH key authentication:

.. code-block:: python

    # Automatic key discovery from ~/.ssh/config
    async with aiodocker.Docker(url="ssh://ubuntu@host:22") as docker:
        containers = await docker.containers.list()

    # Specify custom key file
    from aiodocker.ssh import SSHConnector

    connector = SSHConnector(
        "ssh://ubuntu@host:22",
        client_keys=["~/.ssh/docker_key"]
    )
    async with aiodocker.Docker(connector=connector) as docker:
        containers = await docker.containers.list()

Password Authentication (Discouraged)
--------------------------------------

Passwords can be included in URLs but this is not recommended for security reasons:

.. code-block:: python

    # Warning: Password will be stored in memory and may appear in logs
    async with aiodocker.Docker(url="ssh://ubuntu:password@host:22") as docker:
        containers = await docker.containers.list()

Host Key Verification
=====================

By default, aiodocker enforces strict host key verification for security. The remote host must be present in ``~/.ssh/known_hosts``.

Adding Host Keys
----------------

Add the remote host to your known hosts file:

.. code-block:: bash

    # Method 1: Connect manually to add host key
    ssh ubuntu@remote-host

    # Method 2: Add host key directly
    ssh-keyscan -H remote-host >> ~/.ssh/known_hosts

    # Method 3: Copy from another trusted machine
    scp trusted-machine:~/.ssh/known_hosts ~/.ssh/known_hosts

Relaxing Host Key Verification
-------------------------------

For testing environments only, you can disable strict host key checking:

.. code-block:: python

    from aiodocker.ssh import SSHConnector

    # WARNING: Only for testing - vulnerable to man-in-the-middle attacks
    connector = SSHConnector(
        "ssh://ubuntu@test-host:22",
        strict_host_keys=False
    )
    async with aiodocker.Docker(connector=connector) as docker:
        containers = await docker.containers.list()


SSH Configuration
=================

aiodocker automatically reads SSH configuration from ``~/.ssh/config`` when the ``paramiko`` library is available.

Example SSH config:

.. code-block:: text

    Host docker-prod
        HostName production.example.com
        User dockeruser
        Port 2222
        IdentityFile ~/.ssh/docker_prod_key
        UserKnownHostsFile ~/.ssh/known_hosts_prod

    Host docker-staging
        HostName staging.example.com
        User ubuntu
        Port 22
        IdentityFile ~/.ssh/docker_staging_key

Usage with SSH config:

.. code-block:: python

    # Automatically uses settings from ~/.ssh/config
    async with aiodocker.Docker(url="ssh://docker-prod") as docker:
        containers = await docker.containers.list()

Advanced Configuration
======================

Custom SSH Options
-------------------

Pass additional SSH options directly to the underlying asyncssh connection:

.. code-block:: python

    from aiodocker.ssh import SSHConnector

    connector = SSHConnector(
        "ssh://ubuntu@host:22",
        # Custom SSH options
        compression=True,
        keepalive_interval=30,
        known_hosts="/custom/path/known_hosts"
    )
    async with aiodocker.Docker(connector=connector) as docker:
        containers = await docker.containers.list()

Connection Reuse
----------------

For better performance, reuse the same connector across multiple Docker instances:

.. code-block:: python

    from aiodocker.ssh import SSHConnector

    # Create connector once
    connector = SSHConnector("ssh://ubuntu@host:22")

    # Reuse across multiple Docker instances
    async with aiodocker.Docker(connector=connector) as docker1:
        containers = await docker1.containers.list()

    async with aiodocker.Docker(connector=connector) as docker2:
        images = await docker2.images.list()

    # Clean up when done
    await connector.close()

Security Considerations
=======================

The SSH implementation follows security best practices:

Environment Sanitization
-------------------------

Potentially dangerous environment variables are automatically removed from SSH connections:

* ``LD_LIBRARY_PATH``
* ``SSL_CERT_FILE``
* ``SSL_CERT_DIR``
* ``PYTHONPATH``

Credential Protection
---------------------

* Passwords are cleared from memory after successful connection
* Error messages sanitize credential information to prevent leakage
* Log messages are filtered to avoid password exposure

Secure Temporary Files
----------------------

Local socket files are created in secure temporary directories with restricted permissions (mode 0700), ensuring only the current user can access them.

Troubleshooting
===============

Common Issues
-------------

**"Host key verification failed"**

Add the host to your known hosts file:

.. code-block:: bash

    ssh-keyscan -H hostname >> ~/.ssh/known_hosts

**"Permission denied (publickey)"**

Ensure your SSH key is properly configured:

.. code-block:: bash

    ssh-add ~/.ssh/your_key
    ssh ubuntu@hostname  # Test SSH connection manually

**"Connection refused"**

Verify the SSH service is running and accessible:

.. code-block:: bash

    telnet hostname 22

Debugging
---------

Enable debug logging to troubleshoot connection issues:

.. code-block:: python

    import logging
    logging.basicConfig(level=logging.DEBUG)

    async with aiodocker.Docker(url="ssh://ubuntu@host:22") as docker:
        containers = await docker.containers.list()

Requirements
============

* ``asyncssh >= 2.14.0`` (installed automatically with ``aiodocker[ssh]``)
* SSH access to the remote Docker host
* Docker CLI (``docker`` command) available on the remote host (required for ``docker system dial-stdio``)
* Docker daemon running and accessible on the remote host

----------
Reference
----------

SSHConnector
============

.. autoclass:: aiodocker.ssh.SSHConnector
        :members:
        :undoc-members:
