import logging
from typing import Any, Optional
import yaml

MAX_CPU_CORES = 32

class GlyphConfig:
    _config: dict
    __instance = None

    def __new__(cls):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    def __init__(self) -> None:
        logging.basicConfig(
            filename="glyph_log.log", encoding="utf-8", level=logging.INFO
        )

    @staticmethod
    def load_config() -> bool:
        try:
            with open("config.yml", "r", encoding="utf-8") as f:
                GlyphConfig._config = yaml.safe_load(f) or {}
            return True
        except FileNotFoundError:
            logging.error("config.yml not found.")
            return False
        except yaml.YAMLError as e:
            logging.error("Failed to parse config.yml: %s", e)
            return False

    @staticmethod
    def get_config_value(value: str) -> Optional[Any]:
        return GlyphConfig._config.get(value)

    @staticmethod
    def set_max_file_size(size: int) -> bool:
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
            return False

        if size < 1:
            logging.error("Attempted to set a file size of 0 MB or smaller.")
            return False

        if size > 2048:
            logging.error("Attempted to set a maximum file size greater than 2048 MB.")
            return False

        GlyphConfig._config["max_file_size_mb"] = size

        return True

    @staticmethod
    def set_cpu_cores(cores: int) -> bool:
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

        if cores <= 0:
            logging.error("Attempted to set a non-positive or 0 number of CPU cores.")
            return False

        if cores > 32:
            logging.error("Attempted to set more than 32 CPU cores.")
            return False

        GlyphConfig._config["cpu_cores"] = cores
        return True
