"""SSH connector for aiodocker."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

import aiohttp


try:
    import asyncssh
except ImportError:
    asyncssh = None

# Try to import SSH config parser (preferably paramiko like docker-py)
try:
    from paramiko import SSHConfig
except ImportError:
    SSHConfig = None

log = logging.getLogger(__name__)

# Constants
DEFAULT_SSH_PORT = 22
DEFAULT_DOCKER_SOCKET = "/var/run/docker.sock"
DANGEROUS_ENV_VARS = ["LD_LIBRARY_PATH", "SSL_CERT_FILE", "SSL_CERT_DIR", "PYTHONPATH"]

__all__ = ["SSHConnector", "parse_ssh_url"]


class SSHConnector(aiohttp.UnixConnector):
    """SSH tunnel connector that forwards Docker socket connections over SSH."""

    def __init__(
        self,
        ssh_url: str,
        socket_path: str = DEFAULT_DOCKER_SOCKET,
        strict_host_keys: bool = True,
        **kwargs: Any,
    ):
        """Initialize SSH connector.

        Args:
            ssh_url: SSH connection URL (ssh://user@host:port)
            socket_path: Remote Docker socket path
            strict_host_keys: Enforce strict host key verification (default: True)
            **kwargs: Additional SSH connection options
        """
        if asyncssh is None:
            raise ImportError(
                "asyncssh is required for SSH connections. "
                "Install with: pip install aiodocker[ssh]"
            )

        # Validate and parse SSH URL
        parsed = urlparse(ssh_url)
        if parsed.scheme != "ssh":
            raise ValueError(f"Invalid SSH URL scheme: {parsed.scheme}")

        if not parsed.hostname:
            raise ValueError("SSH URL must include hostname")

        if not parsed.username:
            raise ValueError("SSH URL must include username")

        self._ssh_host = parsed.hostname
        self._ssh_port = parsed.port or DEFAULT_SSH_PORT
        self._ssh_username = parsed.username
        self._ssh_password = parsed.password
        self._socket_path = socket_path
        self._strict_host_keys = strict_host_keys

        # Validate port range
        if not (1 <= self._ssh_port <= 65535):
            raise ValueError(f"Invalid SSH port: {self._ssh_port}")

        # Load SSH config and merge with provided options
        ssh_config = self._load_ssh_config()
        self._ssh_options = {**ssh_config, **kwargs}

        # Validate and enforce host key verification
        self._setup_host_key_verification()

        # Warn about password in URL
        if self._ssh_password:
            log.warning(
                "Password provided in SSH URL. Consider using SSH key authentication "
                "for better security. Passwords may be exposed in logs or memory dumps."
            )

        # Connection state
        self._ssh_conn: Optional[asyncssh.SSHClientConnection] = None
        self._ssh_context: Optional[Any] = None
        self._tunnel_lock = asyncio.Lock()

        # Create secure temporary directory (system chooses location and sets permissions)
        try:
            self._temp_dir = Path(tempfile.mkdtemp())
            self._local_socket_path = str(self._temp_dir / "docker.sock")
        except Exception:
            # Clean up if temp directory creation fails
            if hasattr(self, "_temp_dir") and self._temp_dir.exists():
                shutil.rmtree(self._temp_dir, ignore_errors=True)
            raise

        # Initialize as Unix connector with our local socket
        super().__init__(path=self._local_socket_path)

    def _load_ssh_config(self) -> Dict[str, Any]:
        """Load SSH configuration from ~/.ssh/config like docker-py does."""
        if SSHConfig is None:
            log.debug("SSH config parsing not available (paramiko not installed)")
            return {}

        config_options = {}
        ssh_config_path = Path.home() / ".ssh" / "config"

        if ssh_config_path.exists():
            try:
                config = SSHConfig()
                with ssh_config_path.open() as f:
                    config.parse(f)
                host_config = config.lookup(self._ssh_host)

                # Map SSH config options to asyncssh parameters
                # Only use config port if not specified in URL
                if "port" in host_config and self._ssh_port == DEFAULT_SSH_PORT:
                    self._ssh_port = int(host_config["port"])
                # Only use config user if not specified in URL
                if "user" in host_config and not self._ssh_username:
                    self._ssh_username = host_config["user"]
                # Map file paths directly
                if "identityfile" in host_config:
                    config_options["client_keys"] = host_config["identityfile"]
                if "userknownhostsfile" in host_config:
                    config_options["known_hosts"] = host_config["userknownhostsfile"]

                log.debug(f"Loaded SSH config for {self._ssh_host}")

            except Exception as e:
                log.warning(f"Failed to parse SSH config: {e}")

        return config_options

    def _setup_host_key_verification(self) -> None:
        """Setup host key verification following docker-py security principles."""
        known_hosts = self._ssh_options.get("known_hosts")

        # If no known_hosts specified in config, use default location
        if known_hosts is None:
            default_known_hosts = Path.home() / ".ssh" / "known_hosts"
            if default_known_hosts.exists():
                self._ssh_options["known_hosts"] = str(default_known_hosts)
                known_hosts = str(default_known_hosts)

        if known_hosts is None and self._strict_host_keys:
            # Docker-py equivalent: enforce host key checking
            raise ValueError(
                "Host key verification is required for security. "
                "Either add the host to ~/.ssh/known_hosts or set strict_host_keys=False. "
                "SECURITY WARNING: Disabling host key verification makes connections "
                "vulnerable to man-in-the-middle attacks."
            )
        elif known_hosts is None:
            # Allow but warn (similar to docker-py's WarningPolicy)
            log.warning(
                f"SECURITY WARNING: Host key verification disabled for {self._ssh_host}. "
                "Connection is vulnerable to man-in-the-middle attacks. "
                "Add host to ~/.ssh/known_hosts or run: ssh-keyscan -H %s >> ~/.ssh/known_hosts",
                self._ssh_host,
            )

    def _sanitize_error_message(self, error: Exception) -> str:
        """Sanitize error messages to prevent credential leakage."""
        message = str(error)

        # Remove password from error messages
        if self._ssh_password:
            message = message.replace(self._ssh_password, "***REDACTED***")

        # Remove password from SSH URLs in error messages
        message = re.sub(
            r"ssh://([^:/@]+):([^@]+)@", r"ssh://\1:***REDACTED***@", message
        )

        return message

    def _clean_environment(self) -> Dict[str, str]:
        """Clean environment variables for security like docker-py does."""
        env = os.environ.copy()
        for var in DANGEROUS_ENV_VARS:
            env.pop(var, None)
        return env

    async def _ensure_ssh_tunnel(self) -> None:
        """Ensure SSH tunnel is established using asyncssh context manager with proper locking."""
        # Use lock to prevent concurrent tunnel creation (docker-py principle)
        async with self._tunnel_lock:
            # Re-check condition after acquiring lock
            if self._ssh_conn is None or self._ssh_conn.is_closed():
                log.debug(
                    f"Establishing SSH connection to {self._ssh_username}@{self._ssh_host}:{self._ssh_port}"
                )

                try:
                    # Clean environment like docker-py does
                    clean_env = self._clean_environment()

                    # Use asyncssh context manager properly
                    self._ssh_context = asyncssh.connect(
                        host=self._ssh_host,
                        port=self._ssh_port,
                        username=self._ssh_username,
                        password=self._ssh_password,
                        env=clean_env,
                        **self._ssh_options,
                    )
                    self._ssh_conn = await self._ssh_context.__aenter__()

                    # Forward local socket to remote Docker socket
                    await self._ssh_conn.forward_local_path(
                        self._local_socket_path, self._socket_path
                    )
                    log.debug(
                        f"SSH tunnel established: local socket -> {self._socket_path}"
                    )

                    # Clear password from memory after successful connection
                    if self._ssh_password:
                        self._ssh_password = None

                except Exception as e:
                    sanitized_error = self._sanitize_error_message(e)
                    log.error(f"Failed to establish SSH connection: {sanitized_error}")

                    # Clean up context if it was created
                    if self._ssh_context:
                        try:
                            await self._ssh_context.__aexit__(
                                type(e), e, e.__traceback__
                            )
                        except Exception:
                            pass
                        self._ssh_context = None
                        self._ssh_conn = None
                    raise

    async def connect(
        self, req: aiohttp.ClientRequest, traces: Any, timeout: aiohttp.ClientTimeout
    ) -> aiohttp.ClientResponse:
        """Connect through SSH tunnel."""
        await self._ensure_ssh_tunnel()
        return await super().connect(req, traces, timeout)

    async def close(self) -> None:
        """Close SSH connection and clean up resources with proper error handling."""
        await super().close()

        # Close SSH context manager properly
        if self._ssh_context:
            try:
                await self._ssh_context.__aexit__(None, None, None)
            except Exception as e:
                sanitized_error = self._sanitize_error_message(e)
                log.warning(f"Error closing SSH connection: {sanitized_error}")
            finally:
                self._ssh_context = None
                self._ssh_conn = None

        # Clean up temporary directory (removes socket file automatically)
        try:
            if self._temp_dir.exists():
                shutil.rmtree(self._temp_dir, ignore_errors=True)
        except Exception as e:
            # Don't log full path for security
            temp_name = self._temp_dir.name[-8:] if self._temp_dir.name else "unknown"
            log.warning(
                f"Failed to clean up temporary directory <temp-{temp_name}>: {type(e).__name__}"
            )

        # Clear any remaining sensitive data
        self._ssh_password = None


def parse_ssh_url(url: str) -> Tuple[str, str]:
    """Parse SSH URL and extract connection info and socket path.

    Args:
        url: SSH URL like ssh://user@host:port///path/to/docker.sock

    Returns:
        Tuple of (ssh_connection_url, socket_path)
    """
    if not url.startswith("ssh://"):
        raise ValueError("SSH URL must start with ssh://")

    # Handle the triple slash for absolute path
    if "///" in url:
        ssh_part, socket_path = url.split("///", 1)
        socket_path = "/" + socket_path
    else:
        ssh_part = url
        socket_path = DEFAULT_DOCKER_SOCKET

    return ssh_part, socket_path
