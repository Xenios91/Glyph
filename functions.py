from sql_service import SQLUtil


class FunctionPersistanceUtil():

    @staticmethod
    def get_functions(model_name: str) -> list:
        functions: list = SQLUtil.get_functions(model_name)
        return functions

    @staticmethod
    def delete_function(function_name: str):
        SQLUtil.delete_function(function_name)
