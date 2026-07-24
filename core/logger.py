import os
import logging
from datetime import datetime
from config import LOG_DIR


class LogManager:
    def __init__(self, session_name=None):
        self.session_name = session_name or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = os.path.join(LOG_DIR, f"{self.session_name}.log")
        self._logger = logging.getLogger(f"ucm_{self.session_name}")
        self._logger.setLevel(logging.DEBUG)
        self._logger.handlers.clear()

        fh = logging.FileHandler(self.log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        fh.setFormatter(fmt)
        self._logger.addHandler(fh)

    def info(self, msg):
        self._logger.info(msg)

    def debug(self, msg):
        self._logger.debug(msg)

    def error(self, msg):
        self._logger.error(msg)

    def warning(self, msg):
        self._logger.warning(msg)

    def log(self, msg):
        self.info(msg)

    def get_log_path(self):
        return self.log_file
