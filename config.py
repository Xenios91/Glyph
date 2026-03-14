import logging
from typing import Any, Optional
import yaml


class GlyphConfig():
    _config: dict
    __instance = None

    def __new__(cls):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    def __init__(self) -> None:
        logging.basicConfig(filename="glyph_log.log",
                            encoding="utf-8", level=logging.INFO)

    @classmethod
    def load_config(cls):
        with open("config.yml", 'r', encoding='utf-8') as config:
            cls._config = yaml.safe_load(config)

    @classmethod
    def get_config_value(cls, value: str) -> Optional[Any]:
        return cls._config.get(value)

    @classmethod
    def set_max_file_size(cls, size: int) -> bool:
        """
        Set the maximum file size limit for a file upload.

        Args:
            size (int): The maximum file size in megabytes.

        Returns:
            Bool: True if the maximum file size is set successfully, False otherwise.

        Raises:
            ValueError: If the maximum file size is negative.
            TypeError: If the maximum file size is not an integer.
        """
        if not isinstance(size, int):
            logging.error("Maximum file size must be an integer.")
            return

        if size < 1:
            logging.error("Attempted to set a file size of 0 MB or smaller.")
            return

        if size > 2048:
            logging.error("Attempted to set a maximum file size greater than 2048 MB.")
            return

        cls._config['max_file_size_mb'] = size

    @classmethod
    def set_cpu_cores(cls, cores: int) -> bool:
        """
        Set the number of CPU cores available for analysis.

        Args:
            cores (int): The number of CPU cores to use.

        Returns:
            Bool: True if the number of CPU cores is set successfully, False otherwise.

        Raises:
            ValueError: If the number of CPU cores is negative.
            TypeError: If the number of CPU cores is not an integer.
        """
        if not isinstance(cores, int):
            logging.error("Number of CPU cores must be an integer.")
            return False

        if cores < 0:
            logging.error("Attempted to set a negative number of CPU cores.")
            return False

        if cores > 16:  # This value can be adjusted based on system capabilities
            logging.error("Attempted to set more than 16 CPU cores.")
            return False

        cls._config['cpu_cores'] = cores
        return True
