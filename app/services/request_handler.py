"""Request handler module for processing training and prediction requests."""

import json
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pandas as pd
from loguru import logger


class DataHandler:
    """Base class for handling training and prediction data operations.

    Provides shared functionality for parsing function data from request
    payloads, deduplicating functions, and converting token lists to
    space-separated strings for ML processing.

    Attributes:
        uuid: Unique identifier for this request.
        model_name: Name of the ML model to use.
        json_dict: Raw request data dictionary.
        bin_dictionary: Optional binary metadata dictionary.
        data: Processed DataFrame ready for ML operations.
        status: Current processing status.

    """

    uuid: str
    model_name: str
    json_dict: dict[str, Any]
    bin_dictionary: dict[str, Any] | None = None
    data: pd.DataFrame | None = None
    status: str = "starting"

    def __init__(self, req_uuid: str, data: dict[str, Any], model_name: str) -> None:
        """Initialize the data handler.

        Args:
            req_uuid: Unique identifier for this request.
            data: Raw request data containing functionsMap.
            model_name: Name of the ML model to use.

        """
        self.uuid = req_uuid
        self.model_name = model_name
        self.json_dict = data
        self.status = "starting"
        self._clean_dict()

    def _clean_dict(self) -> None:
        """Remove duplicate functions from the request data while preserving order.

        Deduplicates based on JSON serialization of each function entry,
        ensuring that identical functions are only processed once.
        """
        functions_temp = list(self.get_functions())

        seen: set[str] = set()
        unique_functions: list[dict[str, Any]] = []
        for func in functions_temp:
            func_key = json.dumps(func, sort_keys=True)
            if func_key not in seen:
                seen.add(func_key)
                unique_functions.append(func)
        self.json_dict["functionsMap"]["functions"] = unique_functions

    @staticmethod
    def _deduplicate_functions(functions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Deduplicate functions based on JSON serialization.

        Serializes each function to a JSON string (with sorted keys) to use
        as a deduplication key, then deserializes back. This ensures that
        functions with identical content are treated as duplicates regardless
        of key ordering.

        Args:
            functions: List of function dictionaries to deduplicate.

        Returns:
            Deduplicated list of function dictionaries.

        """
        return [json.loads(t) for t in {json.dumps(d, sort_keys=True) for d in functions}]

    @staticmethod
    def _convert_tokens(functions: list[dict[str, Any]]) -> None:
        """Convert token lists to space-separated strings in place.

        For each function dictionary, reads the "tokenList" field and joins
        it into a single space-separated string stored in the "tokens" field.

        Args:
            functions: List of function dictionaries to process (modified in place).

        """
        for function in functions:
            token_list = function["tokenList"]
            tokens = " ".join(cast(list[str], token_list))
            function["tokens"] = tokens

    def _load_data(self, error_label: str) -> None:
        """Load and process function data into a DataFrame.

        Shared implementation used by TrainingRequest and PredictionRequest.
        Subclasses call this from their own _load_data() with an appropriate
        error label for logging.

        Args:
            error_label: Label used in error messages (e.g., "training", "prediction").

        Raises:
            ValueError: If the data is invalid or processing fails.

        """
        try:
            functions_temp = list(self.get_functions())
            unique_functions = self._deduplicate_functions(functions_temp)
            self._convert_tokens(unique_functions)
            self.data = pd.DataFrame(unique_functions)
        except Exception as load_exception:
            logger.exception("Failed to process %s data", error_label)
            exc = ValueError("invalid dataset")
            exc.add_note(f"Error processing {error_label} data for UUID: {self.uuid}")
            raise exc from load_exception

    def get_functions(self) -> list[dict[str, Any]]:
        """Get the list of functions from the request data.

        Returns:
            List of function dictionaries from the functionsMap.

        """
        return cast(list[dict[str, Any]], self.json_dict["functionsMap"]["functions"])


class TrainingRequest(DataHandler):
    """Handler for ML model training requests.

    Processes binary function data into a DataFrame suitable for
    training a classification model. Each function's token list is
    converted to a space-separated string.
    """

    bin_name: str

    def __init__(self, req_uuid: str, model_name: str, data: dict[str, Any]) -> None:
        """Initialize a training request handler.

        Args:
            req_uuid: Unique identifier for this request.
            model_name: Name of the ML model to train.
            data: Raw request data containing binaryName and functionsMap.

        Raises:
            ValueError: If the training data is invalid.

        """
        super().__init__(req_uuid, data, model_name)
        self._load_data()

    def _load_data(self, error_label: str = "training") -> None:
        """Load and process training data.

        Extracts the binary name and delegates to the shared base
        implementation for function deduplication and token conversion.

        Raises:
            ValueError: If the training data is invalid.

        """
        self.bin_name = self.json_dict["binaryName"]
        super()._load_data(error_label="training")


class PredictionRequest(DataHandler):
    """Handler for ML model prediction requests.

    Processes function data into a DataFrame suitable for running
    predictions against an existing trained model. Each function's
    token list is converted to a space-separated string.

    Attributes:
        task_name: Unique name for this prediction task.

    """

    task_name: str

    def __init__(self, req_uuid: str, model_name: str, data: dict[str, Any]) -> None:
        """Initialize a prediction request handler.

        Args:
            req_uuid: Unique identifier for this request.
            model_name: Name of the trained model to use.
            data: Raw request data containing taskName and functionsMap.

        Raises:
            ValueError: If taskName is missing or prediction data is invalid.

        """
        super().__init__(req_uuid, data, model_name)
        self.task_name = cast(str, data.get("taskName") or data.get("task_name", ""))
        if not self.task_name:
            raise ValueError("Data must contain 'taskName' or 'task_name' key")
        self._load_data()

    def _load_data(self, error_label: str = "prediction") -> None:
        """Load and process prediction data.

        Delegates to base class shared implementation.

        Raises:
            ValueError: If the prediction data is invalid.

        """
        super()._load_data(error_label="prediction")


class GhidraRequest:
    """Request handler for Ghidra binary analysis tasks.

    Encapsulates the metadata needed to run Ghidra decompilation
    and subsequent ML training or prediction on a binary file.

    Attributes:
        file_name: Path to the binary file.
        is_training: Whether this is a training or prediction task.
        model_name: Name of the ML model.
        name: Human-readable task name.
        ml_class_type: Machine learning classification type.
        uuid: Unique identifier for this request.

    """

    file_name: str
    is_training: bool
    model_name: str
    name: str
    ml_class_type: str
    uuid: str

    def __init__(self, filename: str, is_training: bool, model_name: str, name: str, ml_class_type: str) -> None:
        """Initialize a Ghidra analysis request.

        Args:
            filename: Path to the binary file to analyze.
            is_training: True for training, False for prediction.
            model_name: Name of the ML model.
            name: Human-readable task name.
            ml_class_type: Machine learning classification type.

        """
        self.file_name = Path(filename).as_posix()
        self.is_training = is_training
        self.model_name = model_name
        self.name = name
        self.ml_class_type = ml_class_type
        self.uuid = str(uuid4())


class Prediction:
    """Data class for storing prediction results.

    Attributes:
        model_name: Name of the model used for prediction.
        task_name: Name of the prediction task.
        predictions: List of prediction result dictionaries.

    """

    model_name: str
    task_name: str
    predictions: list[dict[str, Any]]

    def __init__(self, task_name: str, model_name: str, pred: list[dict[str, Any]]) -> None:
        """Initialize a prediction result.

        Args:
            task_name: Name of the prediction task.
            model_name: Name of the model used.
            pred: List of prediction result dictionaries.

        """
        self.task_name = task_name
        self.model_name = model_name
        self.predictions = pred
