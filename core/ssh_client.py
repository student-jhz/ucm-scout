import time
import threading
import paramiko

from config import DEFAULT_SSH_PORT, DEFAULT_SSH_TIMEOUT, DEFAULT_COMMAND_TIMEOUT


class SSHClient:
    def __init__(self, host, port=DEFAULT_SSH_PORT, username="", password=""):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self._client = None
        self._sftp = None
        self._connected = False

    def connect(self, timeout=None):
        if timeout is None:
            timeout = DEFAULT_SSH_TIMEOUT
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._client.connect(
            hostname=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            timeout=timeout,
            allow_agent=False,
            look_for_keys=False,
        )
        self._sftp = self._client.open_sftp()
        self._connected = True

    def disconnect(self):
        if self._sftp:
            self._sftp.close()
        if self._client:
            self._client.close()
        self._connected = False

    @property
    def connected(self):
        return self._connected

    def upload_file(self, local_path, remote_path):
        self._sftp.put(local_path, remote_path)

    def execute(self, command, on_stdout=None, on_stderr=None, timeout=DEFAULT_COMMAND_TIMEOUT):
        transport = self._client.get_transport()
        channel = transport.open_session()
        channel.exec_command(command)

        stdout_lines = []
        stderr_lines = []

        def _read_stream(stream, callback, collector):
            for line in iter(stream.readline, ""):
                if line:
                    collector.append(line)
                    if callback:
                        callback(line.strip())

        stdout_thread = threading.Thread(
            target=_read_stream,
            args=(channel.makefile("r"), on_stdout, stdout_lines),
            daemon=True,
        )
        stderr_thread = threading.Thread(
            target=_read_stream,
            args=(channel.makefile_stderr("r"), on_stderr, stderr_lines),
            daemon=True,
        )
        stdout_thread.start()
        stderr_thread.start()

        start = time.time()
        while not channel.exit_status_ready():
            if timeout and time.time() - start > timeout:
                channel.close()
                raise TimeoutError(f"command timed out after {timeout}s")
            time.sleep(0.1)

        stdout_thread.join(timeout=5)
        stderr_thread.join(timeout=5)

        exit_code = channel.recv_exit_status()
        return exit_code, "".join(stdout_lines), "".join(stderr_lines)

    def test_connection(self):
        code, out, err = self.execute("echo ok && uname -a", timeout=10)
        return code == 0, out.strip()
