from request_handler import PredictionRequest
from sql_service import SQLUtil


class FunctionPersistanceUtil():

    @staticmethod
    def get_functions(model_name: str) -> list:
        functions: list = SQLUtil.get_functions(model_name)
        return functions

    @staticmethod
    def delete_function(function_name: str):
        SQLUtil.delete_function(function_name)

    @staticmethod
    def add_functions(prediction_request: PredictionRequest, predictions):
        functions = prediction_request.json_dict['functionsMap']["functions"]
        for ctr, function in enumerate(functions):
            function["functionName"] = predictions[ctr]
        SQLUtil.save_functions(prediction_request.model_name, function)
