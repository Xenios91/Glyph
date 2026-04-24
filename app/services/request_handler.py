"""Request handler module for processing training and prediction requests."""

import json
from uuid import uuid4
from typing import Any, cast
from pathlib import Path
import pandas as pd

from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class DataHandler:
    """Base class for handling data operations."""

    uuid: str
    model_name: str
    json_dict: dict[str, Any]
    bin_dictionary: dict[str, Any] | None = None
    data: pd.DataFrame | None = None
    status: str = "starting"

    def __init__(self, req_uuid: str, data: dict[str, Any], model_name: str):
        self.uuid = req_uuid
        self.model_name = model_name
        self.json_dict = data
        self.status = "starting"
        self._clean_dict()

    def _clean_dict(self) -> None:
        """Remove duplicate functions from the request data while preserving order."""
        functions_temp = list(self.get_functions())
        # Use dict.fromkeys() to preserve order while deduplicating
        # Python 3.7+ guarantees dict insertion order is preserved
        seen = set()
        unique_functions = []
        for func in functions_temp:
            func_key = json.dumps(func, sort_keys=True)
            if func_key not in seen:
                seen.add(func_key)
                unique_functions.append(func)
        self.json_dict["functionsMap"]["functions"] = unique_functions

    def _load_data(self) -> None:
        """Load and process data. Override in subclasses."""

    def get_functions(self) -> list[dict[str, Any]]:
        """Get the list of functions from the request data.

        Returns:
            List of function dictionaries.
        """
        return self.json_dict["functionsMap"]["functions"]


class TrainingRequest(DataHandler):
    """Handler for training requests."""

    bin_name: str

    def __init__(self, req_uuid: str, model_name: str, data: dict[str, Any]) -> None:
        super().__init__(req_uuid, data, model_name)
        self._load_data()

    def _load_data(self) -> None:
        """Load and process training data.

        Raises:
            ValueError: If the training data is invalid.
        """
        try:
            self.bin_name = self.json_dict["binaryName"]
            functions_temp = list(self.get_functions())
            unique_functions = [
                json.loads(t)
                for t in {json.dumps(d, sort_keys=True) for d in functions_temp}
            ]

            for function in unique_functions:
                token_list = function["tokenList"]
                tokens = " ".join(cast(list[str], token_list))
                function["tokens"] = tokens

            self.data = pd.DataFrame(unique_functions)
        except Exception as tr_exception:
            exc = ValueError("invalid dataset")
            exc.add_note(f"Error processing training data for UUID: {self.uuid}")
            raise exc from tr_exception


class PredictionRequest(DataHandler):
    """Handler for prediction requests."""

    task_name: str

    def __init__(self, req_uuid: str, model_name: str, data: dict[str, Any]) -> None:
        super().__init__(req_uuid, data, model_name)
        self.task_name = data["taskName"]
        self._load_data()

    def _load_data(self) -> None:
        """Load and process prediction data.

        Raises:
            ValueError: If the prediction data is invalid.
        """
        try:
            functions_temp = list(self.get_functions())
            unique_functions = [
                json.loads(t)
                for t in {json.dumps(d, sort_keys=True) for d in functions_temp}
            ]

            for function in unique_functions:
                token_list = function["tokenList"]
                tokens = " ".join(cast(list[str], token_list))
                function["tokens"] = tokens

            self.data = pd.DataFrame(unique_functions)
        except Exception as unknown_exception:
            logger.error("Error processing prediction data: %s", unknown_exception, exc_info=True)
            exc = ValueError("invalid dataset")
            exc.add_note(f"Error processing prediction data for UUID: {self.uuid}")
            raise exc from unknown_exception


class GhidraRequest:
    """Request handler for Ghidra analysis tasks."""

    file_name: str
    is_training: bool
    model_name: str
    task_name: str
    ml_class_type: str
    uuid: str

    def __init__(
        self,
        filename: str,
        is_training: bool,
        model_name: str,
        task_name: str,
        ml_class_type: str,
    ) -> None:
        self.file_name = Path(filename).as_posix()
        self.is_training = is_training
        self.model_name = model_name
        self.task_name = task_name
        self.ml_class_type = ml_class_type
        self.uuid = str(uuid4())


class Prediction:
    """Data class for prediction results."""

    model_name: str
    task_name: str
    predictions: list[dict[str, Any]]

    def __init__(
        self, task_name: str, model_name: str, pred: list[dict[str, Any]]
    ) -> None:
        self.task_name = task_name
        self.model_name = model_name
        self.predictions = pred
