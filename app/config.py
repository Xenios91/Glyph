import logging
from typing import Any
import yaml
import os

MAX_CPU_CORES = os.cpu_count() or 1


class GlyphConfig:
    _config: dict[str, Any] = {}
    _initialized = False

    @staticmethod
    def load_config() -> bool:
        if not GlyphConfig._initialized:
            logging.basicConfig(
                filename="glyph_log.log", encoding="utf-8", level=logging.INFO
            )

        try:
            with open("config.yml", "r", encoding="utf-8") as f:
                GlyphConfig._config = yaml.safe_load(f) or {}

            GlyphConfig._config["UPLOAD_FOLDER"] = "./binaries"
            GlyphConfig._initialized = True
            return True
        except FileNotFoundError:
            logging.error("config.yml not found.")
            return False
        except yaml.YAMLError as e:
            logging.error("Failed to parse config.yml: %s", e)
            return False

    @staticmethod
    def get_config_value(value: str) -> Any | None:
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

        if cores > MAX_CPU_CORES:
            logging.error("Attempted to set more than %d CPU cores.", MAX_CPU_CORES)
            return False

        GlyphConfig._config["cpu_cores"] = cores
        return True
