import pandas as pd


class DataHandler():
    uuid: str
    model_name: str
    json_dict: str
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

    def __init__(self, uuid: str, data: str, model_name: str):
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

    def __init__(self, uuid: str, model_name: str,  data: str):
        super().__init__(uuid, data, model_name)
        self.task_name = data["binaryName"]
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
        except Exception as p_exception:
            print(p_exception)
            raise Exception("invalid dataset") from p_exception

    def set_prediction_values(self, labels: list[str]):
        functions = self.get_functions()
        for ctr, function in enumerate(functions):
            function["functionName"] = labels[ctr]


class GhidraRequest():
    file_name: str
    is_training: bool
    model_name: str
    ml_class_type: int

    def __init__(self, filename: str, istraining: bool, modelname: str, mlclasstype: str) -> None:
        self.file_name = filename
        self.is_training = istraining
        self.model_name = modelname
        self.ml_class_type = mlclasstype
