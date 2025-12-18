#!/usr/bin/env python3
"""Advanced SSH Docker example demonstrating comprehensive operations."""

import argparse
import asyncio
import logging
import sys
import textwrap
import urllib.parse

import aiodocker


async def demonstrate_ssh_docker(docker_host: str):
    """Connect to Docker over SSH and demonstrate various operations."""
    # Configure logging to see detailed operations
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # SECURITY NOTE: This example assumes the remote host is already in ~/.ssh/known_hosts
    # Add your host with: ssh-keyscan -H hostname >> ~/.ssh/known_hosts

    print(f"Connecting to Docker via SSH: {docker_host}")
    print("=" * 60)

    try:
        async with aiodocker.Docker(url=docker_host) as docker:
            print("SSH connection established successfully!")
            print()

            # 1. Get Docker info
            print("Getting Docker system information...")
            try:
                info = await docker.system.info()
                print(f"Docker Engine Version: {info.get('ServerVersion', 'Unknown')}")
                print(f"   Architecture: {info.get('Architecture', 'Unknown')}")
                print(f"   Operating System: {info.get('OperatingSystem', 'Unknown')}")
                print(f"   Kernel Version: {info.get('KernelVersion', 'Unknown')}")
                print(f"   Total Memory: {info.get('MemTotal', 0) / (1024**3):.2f} GB")
                print(f"   CPUs: {info.get('NCPU', 'Unknown')}")
                print()
            except Exception as e:
                print(f"Failed to get Docker info: {e}")
                print()

            # 2. List containers
            print("Listing containers...")
            try:
                containers = await docker.containers.list(
                    all=True
                )  # Include stopped containers
                print(f"Found {len(containers)} containers:")

                if containers:
                    for container in containers:
                        container_info = await container.show()
                        name = container_info["Name"].lstrip("/")
                        image = container_info["Config"]["Image"]
                        state = container_info["State"]["Status"]
                        print(f"   • {name:<20} | {image:<30} | {state}")
                else:
                    print("   No containers found")
                print()
            except Exception as e:
                print(f"Failed to list containers: {e}")
                print()

            # 3. List images
            print("Listing available images...")
            try:
                images = await docker.images.list()
                print(f"Found {len(images)} images:")

                if images:
                    for image in images:
                        # Get image details
                        image_id = image["Id"][:12]  # Short ID
                        repo_tags = image.get("RepoTags", ["<none>:<none>"])
                        if repo_tags and repo_tags[0] != "<none>:<none>":
                            tag = repo_tags[0]
                        else:
                            tag = "<none>:<none>"
                        size = image.get("Size", 0) / (1024**2)  # MB

                        print(f"   • {image_id} | {tag:<40} | {size:>8.1f} MB")
                else:
                    print("   No images found")
                print()
            except Exception as e:
                print(f"Failed to list images: {e}")
                print()

            # 4. Pull a new image
            print("Pulling a new image...")
            try:
                print("   Pulling alpine:latest...")
                await docker.images.pull("alpine:latest")
                print("Successfully pulled alpine:latest")
                print()
            except Exception as e:
                print(f"Failed to pull image: {e}")
                print()

            # 5. Run a container
            print("Running a new container...")
            container = None  # type: ignore
            try:
                container = await docker.containers.run(
                    config={
                        "Image": "alpine:latest",
                        "Cmd": ["echo", "Hello from SSH Docker!"],
                        "AttachStdout": True,
                        "AttachStderr": True,
                    },
                    name="ssh-test-container",
                )
                print("Container created and started")

                # Wait for container to complete and get logs
                await container.wait()
                logs = await container.log(stdout=True, stderr=True)
                if logs and len(logs) > 0:
                    if isinstance(logs[0], bytes):
                        output = logs[0].decode().strip()
                    else:
                        output = str(logs[0]).strip()
                    print(f"   Container output: {output}")
                else:
                    print("   Container completed (no output captured)")
                print()
            except Exception as e:
                print(f"Failed to run container: {e}")
                print()

            # 6. List containers again to see our new one
            print("Listing containers after running new one...")
            try:
                containers = await docker.containers.list(all=True)
                print(f"Found {len(containers)} containers:")
                for container_item in containers:
                    container_info = await container_item.show()
                    name = container_info["Name"].lstrip("/")
                    image = container_info["Config"]["Image"]
                    state = container_info["State"]["Status"]
                    print(f"   • {name:<25} | {image:<30} | {state}")
                print()
            except Exception as e:
                print(f"Failed to list containers: {e}")
                print()

            # 7. Clean up - delete the test container
            print("Cleaning up test container...")
            try:
                if container:
                    await container.delete()
                    print("Test container deleted successfully")
                else:
                    # Find and delete by name if container object not available
                    containers = await docker.containers.list(all=True)
                    for c in containers:
                        info = await c.show()
                        if info["Name"] == "/ssh-test-container":
                            await c.delete()
                            print("Test container found and deleted")
                            break
                print()
            except Exception as e:
                print(f"Failed to delete container: {e}")
                print()

            # 8. List images again to see the newly pulled one
            print("Final image list...")
            try:
                images = await docker.images.list()
                print(f"Found {len(images)} images:")
                for image in images:
                    image_id = image["Id"][:12]
                    repo_tags = image.get("RepoTags", ["<none>:<none>"])
                    if repo_tags and repo_tags[0] != "<none>:<none>":
                        tag = repo_tags[0]
                    else:
                        tag = "<none>:<none>"
                    size = image.get("Size", 0) / (1024**2)
                    print(f"   • {image_id} | {tag:<40} | {size:>8.1f} MB")
                print()
            except Exception as e:
                print(f"Failed to list images: {e}")
                print()

            # 9. Optional: Clean up the pulled image (commented out to avoid affecting registry)
            # print("Cleaning up pulled image...")
            # try:
            #     await docker.images.delete("alpine:latest")
            #     print("Alpine image deleted")
            # except Exception as e:
            #     print(f"Failed to delete image: {e}")

            print("Comprehensive SSH Docker test completed successfully!")

    except ImportError:
        print("SSH support requires asyncssh. Install with: pip install aiodocker[ssh]")
        sys.exit(1)
    except ValueError as e:
        error_msg = str(e)
        if "Host key verification is required" in error_msg:
            # Extract hostname from docker_host for the commands
            parsed = urllib.parse.urlparse(docker_host)
            hostname = parsed.hostname
            port = parsed.port if parsed.port else 22

            print(
                textwrap.dedent(f"""
                SSH Host Key Verification Failed
                ==================================================
                Security Issue: The remote host is not in your known_hosts file.

                To fix this, add the host key using one of these methods:

                   Method 1 - Add host key automatically:
                   ssh-keyscan -H {hostname} >> ~/.ssh/known_hosts

                   Method 2 - Connect manually first (will prompt to add):
                   ssh {parsed.username}@{hostname} -p {port}

                   Method 3 - Add with specific port:
                   ssh-keyscan -H -p {port} {hostname} >> ~/.ssh/known_hosts

                SECURITY WARNING: Never disable host key verification in production!
                   This protects against man-in-the-middle attacks.
                """).strip()
            )
        else:
            print(f"Configuration Error: {e}")
        sys.exit(1)
    except ConnectionError as e:
        print(
            textwrap.dedent(f"""
            SSH Connection Failed
            ==============================
            Network Issue: {e}

            Troubleshooting steps:
               1. Verify the hostname and port are correct
               2. Check if SSH service is running on the remote host
               3. Ensure you have network connectivity
               4. Verify your SSH credentials/keys are set up
            """).strip()
        )
        sys.exit(1)
    except Exception as e:
        print(
            textwrap.dedent(f"""
            Unexpected Error: {e}

            For debugging, try running with verbose mode:
               python {sys.argv[0]} -v {docker_host}
            """).strip()
        )
        sys.exit(1)


def main():
    """Main function to parse arguments and run the SSH Docker demonstration."""
    parser = argparse.ArgumentParser(
        description="Advanced SSH Docker operations demonstration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s ssh://ubuntu@docker-host.example.com:22
  %(prog)s ssh://user@192.168.1.100:2222
  %(prog)s ssh://admin@prod-docker:22

Note:
  - Uses 'docker system dial-stdio' for connections
  - Automatically discovers the correct Docker socket on the remote host
  - Works with standard, rootless, and custom Docker setups

Security Notes:
  - Ensure the remote host is in your ~/.ssh/known_hosts file
  - Use SSH key authentication for better security
  - Add host keys with: ssh-keyscan -H hostname >> ~/.ssh/known_hosts
        """,
    )
    parser.add_argument(
        "docker_host", help="SSH URL for Docker host (e.g., ssh://user@host:port)"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Validate SSH URL format
    if not args.docker_host.startswith("ssh://"):
        print("Error: Docker host must be an SSH URL (ssh://user@host:port)")
        sys.exit(1)

    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Run the demonstration
    asyncio.run(demonstrate_ssh_docker(args.docker_host))


if __name__ == "__main__":
    main()
