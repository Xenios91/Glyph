import pandas as pd


class DataHandler():
    uuid: str
    json_dict: str
    bin_dictionary: dict
    data: pd.DataFrame
    status: str

    def __init__(self, uuid: str, data: dict):
        self.uuid = uuid
        self.json_dict = data
        self.status = "starting"

    def load_data(self):
        pass


class TrainingRequest(DataHandler):
    bin_name: str

    def __init__(self, uuid: str, data: str):
        super().__init__(uuid, data)
        self.load_data()

    def load_data(self):
        try:
            self.bin_name = self.json_dict["binaryName"]
            functions: dict = self.json_dict['functionsMap']["functions"]
            for function in functions:
                token_list = function['tokenList']
                tokens = " ".join(token_list)
                function["tokens"] = tokens
            self.data = pd.DataFrame(functions)
        except Exception as tr_exception:
            raise Exception("invalid dataset") from tr_exception


class PredictionRequest(DataHandler):
    task_name: str
    model_name: str
    uuid: str
    json_dict: dict
    data: pd.DataFrame
    status: str

    def __init__(self, uuid: str, model_name: str,  data: str):
        super().__init__(uuid, data)
        self.model_name = model_name
        self.load_data()

    def load_data(self):
        try:
            functions: dict = self.json_dict['functionsMap']["functions"]
            for function in functions:
                token_list = function['tokenList']
                tokens = " ".join(token_list)
                function["tokens"] = tokens
            self.data = pd.DataFrame(functions)
        except Exception as p_exception:
            print(p_exception)
            raise Exception("invalid dataset") from p_exception