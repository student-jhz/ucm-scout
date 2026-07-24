import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
REMOTE_SCRIPT_DIR = os.path.join(BASE_DIR, "remote_scripts")

DEFAULT_SSH_PORT = 22
DEFAULT_SSH_TIMEOUT = 30
DEFAULT_COMMAND_TIMEOUT = 600

os.makedirs(LOG_DIR, exist_ok=True)
