#!/usr/bin/env python3
"""Example of using aiodocker with SSH connections."""

import asyncio
import logging

import aiodocker


async def main():
    """Connect to Docker over SSH and show system info."""
    # Configure logging to see connection details
    logging.basicConfig(level=logging.DEBUG)

    # Connect to Docker over SSH
    # Format: ssh://user@host:port
    # The connection uses 'docker system dial-stdio' which automatically
    # discovers the correct Docker socket on the remote host
    docker_host = "ssh://ubuntu@docker-host:22"

    # Note: Socket paths in URLs (e.g., ssh://user@host///path) are accepted
    # for backward compatibility but are ignored. The dial-stdio approach
    # automatically works with standard, rootless, and custom Docker setups.

    try:
        async with aiodocker.Docker(url=docker_host) as docker:
            # Get Docker version info
            version = await docker.version()
            print(f"Docker version: {version['Version']}")

            # List containers
            containers = await docker.containers.list()
            print(f"Found {len(containers)} containers")

            # List images
            images = await docker.images.list()
            print(f"Found {len(images)} images")

    except ImportError:
        print("SSH support requires asyncssh. Install with: pip install aiodocker[ssh]")
    except Exception as e:
        print(f"Error connecting over SSH: {e}")


if __name__ == "__main__":
    asyncio.run(main())
