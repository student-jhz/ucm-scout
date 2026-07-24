import unittest
from unittest.mock import MagicMock, patch, PropertyMock
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.ssh_client import SSHClient


class TestSSHClient(unittest.TestCase):
    def setUp(self):
        self.client = SSHClient("testhost", 22, "testuser", "testpass")

    def test_init_defaults(self):
        c = SSHClient("host1")
        self.assertEqual(c.host, "host1")
        self.assertEqual(c.port, 22)
        self.assertEqual(c.username, "")
        self.assertEqual(c.password, "")
        self.assertFalse(c.connected)

    def test_init_custom(self):
        c = SSHClient("host2", 2222, "user", "pass")
        self.assertEqual(c.host, "host2")
        self.assertEqual(c.port, 2222)
        self.assertEqual(c.username, "user")
        self.assertEqual(c.password, "pass")

    @patch("core.ssh_client.paramiko.SSHClient")
    def test_connect(self, mock_ssh_class):
        mock_ssh = MagicMock()
        mock_sftp = MagicMock()
        mock_ssh.open_sftp.return_value = mock_sftp
        mock_ssh_class.return_value = mock_ssh

        c = SSHClient("test", 22, "u", "p")
        c.connect()

        mock_ssh.connect.assert_called_once()
        self.assertTrue(c.connected)

    @patch("core.ssh_client.paramiko.SSHClient")
    def test_connect_failure(self, mock_ssh_class):
        mock_ssh = MagicMock()
        mock_ssh.connect.side_effect = Exception("Connection refused")
        mock_ssh_class.return_value = mock_ssh

        c = SSHClient("bad", 22, "u", "p")
        with self.assertRaises(Exception):
            c.connect()
        self.assertFalse(c.connected)

    @patch("core.ssh_client.paramiko.SSHClient")
    def test_disconnect(self, mock_ssh_class):
        mock_ssh = MagicMock()
        mock_sftp = MagicMock()
        mock_ssh.open_sftp.return_value = mock_sftp
        mock_ssh_class.return_value = mock_ssh

        c = SSHClient("test", 22, "u", "p")
        c.connect()
        self.assertTrue(c.connected)
        c.disconnect()
        self.assertFalse(c.connected)
        mock_sftp.close.assert_called_once()
        mock_ssh.close.assert_called_once()

    @patch("core.ssh_client.paramiko.SSHClient")
    def test_execute(self, mock_ssh_class):
        mock_ssh = MagicMock()
        mock_sftp = MagicMock()
        mock_ssh.open_sftp.return_value = mock_sftp

        mock_transport = MagicMock()
        mock_channel = MagicMock()
        mock_ssh.get_transport.return_value = mock_transport
        mock_transport.open_session.return_value = mock_channel
        mock_ssh_class.return_value = mock_ssh

        mock_stdout = MagicMock()
        mock_stdout.readline.side_effect = ["hello\n", ""]
        mock_stderr = MagicMock()
        mock_stderr.readline.side_effect = [""]
        mock_channel.makefile.return_value = mock_stdout
        mock_channel.makefile_stderr.return_value = mock_stderr
        mock_channel.exit_status_ready.side_effect = [False, False, True]
        mock_channel.recv_exit_status.return_value = 0

        c = SSHClient("test", 22, "u", "p")
        c.connect()
        code, out, err = c.execute("ls")

        self.assertEqual(code, 0)
        self.assertIn("hello", out)

    @patch("core.ssh_client.paramiko.SSHClient")
    def test_execute_timeout(self, mock_ssh_class):
        mock_ssh = MagicMock()
        mock_sftp = MagicMock()
        mock_ssh.open_sftp.return_value = mock_sftp

        mock_transport = MagicMock()
        mock_channel = MagicMock()
        mock_ssh.get_transport.return_value = mock_transport
        mock_transport.open_session.return_value = mock_channel
        mock_ssh_class.return_value = mock_ssh

        mock_stdout = MagicMock()
        mock_stdout.readline.return_value = ""
        mock_stderr = MagicMock()
        mock_stderr.readline.return_value = ""
        mock_channel.makefile.return_value = mock_stdout
        mock_channel.makefile_stderr.return_value = mock_stderr
        mock_channel.exit_status_ready.return_value = False

        c = SSHClient("test", 22, "u", "p")
        c.connect()
        with self.assertRaises(TimeoutError):
            c.execute("sleep 100", timeout=1)

    @patch("core.ssh_client.paramiko.SSHClient")
    def test_upload_file(self, mock_ssh_class):
        mock_ssh = MagicMock()
        mock_sftp = MagicMock()
        mock_ssh.open_sftp.return_value = mock_sftp
        mock_ssh_class.return_value = mock_ssh

        c = SSHClient("test", 22, "u", "p")
        c.connect()
        c.upload_file("/local/file.txt", "/remote/file.txt")

        mock_sftp.put.assert_called_once_with("/local/file.txt", "/remote/file.txt")


if __name__ == "__main__":
    unittest.main()
