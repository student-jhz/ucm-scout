import os
import sys


def _get_base_dir():
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = _get_base_dir()
LOG_DIR = os.path.join(BASE_DIR, "logs")
REMOTE_SCRIPT_DIR = os.path.join(BASE_DIR, "remote_scripts")

DEFAULT_SSH_PORT = 22
DEFAULT_SSH_TIMEOUT = 30
DEFAULT_COMMAND_TIMEOUT = 600

os.makedirs(LOG_DIR, exist_ok=True)
