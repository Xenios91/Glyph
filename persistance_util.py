
import pickle

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from request_handler import PredictionRequest, TrainingRequest

from sql_service import SQLUtil


class MLTask():

    @staticmethod
    def get_multi_class_pipeline() -> Pipeline:
        pipeline = Pipeline(
            [('preprocessor', TfidfVectorizer(ngram_range=(2, 4), norm='l2', sublinear_tf=True)),
             ('clf', MultinomialNB(alpha=1e-8))])
        return pipeline

    # not implemented yet, need to check algos
    @staticmethod
    def get_single_class_pipeline() -> Pipeline:
        pipeline = Pipeline(
            [('preprocessor', TfidfVectorizer(ngram_range=(2, 4), norm='l2', sublinear_tf=True)),
             ('clf', MultinomialNB(alpha=1e-8))])
        return pipeline


class MLPersistanceUtil():

    @staticmethod
    def save_model(model_name: str, pipeline: Pipeline):
        serialized_model: bytes = pickle.dumps(pipeline)
        SQLUtil.save_model(model_name, serialized_model)

    @staticmethod
    def load_model(model_name: str) -> Pipeline:
        model: bytes = SQLUtil.get_model(model_name)
        loaded_model = pickle.loads(model[1])
        return loaded_model

    @staticmethod
    def get_models_list() -> list[str]:
        models_list: set[str] = SQLUtil.get_models_list()
        return models_list

    @staticmethod
    def check_name(model_name: str) -> bool:
        models_list: set[str] = SQLUtil.get_models_list()
        return model_name in models_list

    @staticmethod
    def delete_model(model_name: str):
        SQLUtil.delete_model(model_name)


class FunctionPersistanceUtil():

    @staticmethod
    def get_functions(model_name: str) -> list:
        functions: list = SQLUtil.get_functions(model_name)
        return functions

    @staticmethod
    def delete_function(function_name: str):
        SQLUtil.delete_function(function_name)

    @staticmethod
    def add_model_functions(training_request: TrainingRequest):
        functions = training_request.json_dict['functionsMap']["functions"]
        if functions is not None:
            SQLUtil.save_functions(training_request.model_name, functions)

    @staticmethod
    def add_prediction_functions(prediction_request: PredictionRequest, predictions):
        functions = prediction_request.json_dict['functionsMap']["functions"]
        if functions is not None:
            for (ctr, function) in enumerate(functions):
                function["functionName"] = predictions[ctr]
            SQLUtil.save_functions(prediction_request.model_name, functions)
