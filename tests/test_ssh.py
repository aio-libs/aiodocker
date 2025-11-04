"""Tests for SSH connection support."""

import pytest

from aiodocker.ssh import parse_ssh_url


class TestSSHSupport:
    """Test SSH URL parsing and connection setup."""

    def test_parse_ssh_url_with_socket_path(self):
        """Test parsing SSH URL with explicit socket path."""
        url = "ssh://ubuntu@host:22///var/run/docker.sock"
        ssh_url, socket_path = parse_ssh_url(url)

        assert ssh_url == "ssh://ubuntu@host:22"
        assert socket_path == "/var/run/docker.sock"

    def test_parse_ssh_url_with_custom_socket(self):
        """Test parsing SSH URL with custom socket path."""
        url = "ssh://user@example.com:2222///foo/bar/docker.sock"
        ssh_url, socket_path = parse_ssh_url(url)

        assert ssh_url == "ssh://user@example.com:2222"
        assert socket_path == "/foo/bar/docker.sock"

    def test_parse_ssh_url_default_socket(self):
        """Test parsing SSH URL without explicit socket path."""
        url = "ssh://ubuntu@host:22"
        ssh_url, socket_path = parse_ssh_url(url)

        assert ssh_url == "ssh://ubuntu@host:22"
        assert socket_path == "/var/run/docker.sock"

    def test_parse_ssh_url_invalid_scheme(self):
        """Test parsing invalid URL scheme."""
        with pytest.raises(ValueError, match="SSH URL must start with ssh://"):
            parse_ssh_url("http://example.com")

    def test_ssh_connector_import_error(self):
        """Test SSH connector raises ImportError when asyncssh not available."""
        # Mock missing asyncssh
        import aiodocker.ssh

        original_asyncssh = aiodocker.ssh.asyncssh
        aiodocker.ssh.asyncssh = None

        try:
            from aiodocker.ssh import SSHConnector

            with pytest.raises(ImportError, match="asyncssh is required"):
                SSHConnector("ssh://user@host")
        finally:
            aiodocker.ssh.asyncssh = original_asyncssh

    def test_ssh_connector_invalid_url_scheme(self):
        """Test SSH connector rejects invalid URL schemes."""
        with pytest.raises(ValueError, match="Invalid SSH URL scheme"):
            from aiodocker.ssh import SSHConnector

            SSHConnector("http://user@host")

    def test_ssh_connector_missing_hostname(self):
        """Test SSH connector requires hostname."""
        with pytest.raises(ValueError, match="SSH URL must include hostname"):
            from aiodocker.ssh import SSHConnector

            SSHConnector("ssh://user@")

    def test_ssh_connector_missing_username(self):
        """Test SSH connector requires username."""
        with pytest.raises(ValueError, match="SSH URL must include username"):
            from aiodocker.ssh import SSHConnector

            SSHConnector("ssh://host:22")

    def test_ssh_connector_invalid_port(self):
        """Test SSH connector validates port range."""
        with pytest.raises(ValueError, match="Port out of range"):
            from aiodocker.ssh import SSHConnector

            SSHConnector("ssh://user@host:70000")

        with pytest.raises(ValueError, match="Port could not be cast to integer"):
            from aiodocker.ssh import SSHConnector

            SSHConnector("ssh://user@host:-1")
