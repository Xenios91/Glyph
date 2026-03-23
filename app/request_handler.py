import json
import logging
import uuid
from typing import cast
from pathlib import Path
import pandas as pd


class DataHandler:
    """Base class for handling data operations"""

    uuid: str
    model_name: str
    json_dict: dict[str, object]
    bin_dictionary: dict[str, object] | None = None
    data: pd.DataFrame | None = None
    status: str = "starting"

    def __init__(self, uuid: str, data: dict[str, object], model_name: str):
        self.uuid = uuid
        self.model_name = model_name
        self.json_dict = data
        self.status = "starting"
        self._clean_dict()

    def _clean_dict(self) -> None:
        functions_temp = list(self.get_functions())
        unique_functions = [
            json.loads(t)
            for t in {json.dumps(d, sort_keys=True) for d in functions_temp}
        ]
        self.json_dict["functionsMap"]["functions"] = unique_functions

    def _load_data(self) -> None:
        pass

    def get_functions(self) -> list[dict[str, object]]:
        return self.json_dict["functionsMap"]["functions"]


class TrainingRequest(DataHandler):
    bin_name: str

    def __init__(self, uuid: str, model_name: str, data: dict[str, object]) -> None:
        super().__init__(uuid, data, model_name)
        self._load_data()

    def _load_data(self) -> None:
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
            exc.__cause__ = tr_exception
            raise exc


class PredictionRequest(DataHandler):
    task_name: str
    uuid: str
    json_dict: dict[str, object]
    data: pd.DataFrame
    status: str

    def __init__(self, uuid: str, model_name: str, data: dict[str, object]) -> None:
        super().__init__(uuid, data, model_name)
        self.task_name = data["taskName"]
        self._load_data()

    def _load_data(self) -> None:
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
            logging.error(f"Error processing prediction data: {unknown_exception}")
            exc = ValueError("invalid dataset")
            exc.add_note(f"Error processing prediction data for UUID: {self.uuid}")
            exc.__cause__ = unknown_exception
            raise exc

    def set_prediction_values(self, labels: list[str]) -> None:
        functions = self.get_functions()
        for ctr, function in enumerate(functions):
            function["functionName"] = labels[ctr]


class GhidraRequest:
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
        self.file_name = Path(filename).resolve().as_posix()
        self.is_training = is_training
        self.model_name = model_name
        self.task_name = task_name
        self.ml_class_type = ml_class_type
        self.uuid = str(uuid.uuid4())


class Prediction:
    model_name: str
    task_name: str
    predictions: dict[str, object]

    def __init__(
        self, task_name: str, model_name: str, pred: dict[str, object]
    ) -> None:
        self.task_name = task_name
        self.model_name = model_name
        self.predictions = pred
