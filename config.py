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
