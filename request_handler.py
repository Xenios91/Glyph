import logging
import pandas as pd


class DataHandler():
    uuid: str
    model_name: str
    json_dict: dict
    bin_dictionary: dict
    data: pd.DataFrame
    status: str

    def __init__(self, uuid: str, data: dict, model_name: str):
        self.uuid = uuid
        self.model_name = model_name
        self.json_dict = data
        self.status = "starting"
        self._clean_dict()

    def _clean_dict(self):
        functions: list = []
        functions_temp: list = list(
            self.get_functions())
        for function in functions_temp:
            if function not in functions:
                functions.append(function)
        self.json_dict["functionsMap"]["functions"] = functions

    def _load_data(self):
        pass

    def get_functions(self) -> list:
        return self.json_dict["functionsMap"]["functions"]


class TrainingRequest(DataHandler):
    bin_name: str

    def __init__(self, uuid: str, model_name: str,  data: dict):
        super().__init__(uuid, data, model_name)
        self._load_data()

    def _load_data(self):
        try:
            self.bin_name = self.json_dict["binaryName"]
            functions: list = []
            functions_temp: list = list(
                self.get_functions())
            for function in functions_temp:
                if function not in functions:
                    functions.append(function)

            for function in functions:
                token_list = function['tokenList']
                tokens = " ".join(token_list)
                function["tokens"] = tokens
            self.data = pd.DataFrame(functions)
        except Exception as tr_exception:
            raise Exception("invalid dataset") from tr_exception


class PredictionRequest(DataHandler):
    task_name: str
    uuid: str
    json_dict: dict
    data: pd.DataFrame
    status: str

    def __init__(self, uuid: str, model_name: str,  data: dict):
        super().__init__(uuid, data, model_name)
        self.task_name = data["taskName"]
        self._load_data()

    def _load_data(self):
        try:
            functions: list = []
            functions_temp: list = list(
                self.get_functions())
            for function in functions_temp:
                if function not in functions:
                    functions.append(function)

            for function in functions:
                token_list = function['tokenList']
                tokens = " ".join(token_list)
                function["tokens"] = tokens
            self.data = pd.DataFrame(functions)
        except Exception as unknown_exception:
            logging.error(unknown_exception)
            raise Exception("invalid dataset") from unknown_exception

    def set_prediction_values(self, labels: list[str]):
        functions = self.get_functions()
        for ctr, function in enumerate(functions):
            function["functionName"] = labels[ctr]


class GhidraRequest():
    file_name: str
    is_training: bool
    model_name: str
    task_name: str
    ml_class_type: str

    def __init__(self, filename: str, is_training: bool, model_name: str, task_name: str, mlclasstype: str) -> None:
        self.file_name = filename
        self.is_training = is_training
        self.model_name = model_name
        self.task_name = task_name
        self.ml_class_type = mlclasstype


class Prediction():
    model_name: str
    task_name: str
    predictions: dict

    def __init__(self, task_name: str, model_name: str, pred: dict) -> None:
        self.task_name = task_name
        self.model_name = model_name
        self.predictions = pred
