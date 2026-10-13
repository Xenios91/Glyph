"""Request handler module for processing training and prediction requests."""

import json
from typing import Any, cast


class DataHandler:
    """Base class for handling training and prediction data operations.

    Provides shared functionality for parsing function data from request
    payloads, deduplicating functions, and converting token lists to
    space-separated strings for ML processing.

    Attributes:
        uuid: Unique identifier for this request.
        model_name: Name of the ML model to use.
        json_dict: Raw request data dictionary.

    """

    uuid: str
    model_name: str
    json_dict: dict[str, Any]
    user_id: int | None = None

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
        self._convert_tokens(unique_functions)

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

    def get_functions(self) -> list[dict[str, Any]]:
        """Get the list of functions from the request data.

        Returns:
            List of function dictionaries from the functionsMap.

        """
        return cast(list[dict[str, Any]], self.json_dict["functionsMap"]["functions"])


class TrainingRequest(DataHandler):
    """Handler for ML model training requests.

    Processes binary function data for training a classification model.
    Each function's token list is converted to a space-separated string.
    """

    bin_name: str

    def __init__(self, req_uuid: str, model_name: str, data: dict[str, Any]) -> None:
        """Initialize a training request handler.

        Args:
            req_uuid: Unique identifier for this request.
            model_name: Name of the ML model to train.
            data: Raw request data containing binaryName and functionsMap.

        """
        super().__init__(req_uuid, data, model_name)
        self.bin_name = self.json_dict["binaryName"]


class PredictionRequest(DataHandler):
    """Handler for ML model prediction requests.

    Processes function data for running predictions against an existing
    trained model. Each function's token list is converted to a
    space-separated string.

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
            ValueError: If taskName is missing.

        """
        super().__init__(req_uuid, data, model_name)
        self.task_name = cast(str, data.get("taskName") or data.get("task_name", ""))
        if not self.task_name:
            raise ValueError("Data must contain 'taskName' or 'task_name' key")


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
    user_id: int | None

    def __init__(
        self,
        task_name: str,
        model_name: str,
        pred: list[dict[str, Any]],
        user_id: int | None = None,
    ) -> None:
        """Initialize a prediction result.

        Args:
            task_name: Name of the prediction task.
            model_name: Name of the model used.
            pred: List of prediction result dictionaries.
            user_id: Owner of the prediction (None for legacy/unowned).

        """
        self.task_name = task_name
        self.model_name = model_name
        self.predictions = pred
        self.user_id = user_id
