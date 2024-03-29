
import pickle

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline

from request_handler import Prediction, PredictionRequest, TrainingRequest
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


class PredictionPersistanceUtil():

    @staticmethod
    def get_predictions_list() -> list[Prediction]:
        predictions_list: list[Prediction] = SQLUtil.get_predictions_list()
        return predictions_list

    @staticmethod
    def get_predictions(task_name: str, model_name: str) -> Prediction:
        predictions: Prediction = SQLUtil.get_predictions(
            task_name, model_name)
        return predictions

    @staticmethod
    def delete_prediction(task_name: str):
        SQLUtil.delete_prediction(task_name)

    @staticmethod
    def delete_model_predictions(model_name: str):
        SQLUtil.delete_model_predictions(model_name)


class MLPersistanceUtil():

    @staticmethod
    def save_model(model_name: str, label_encoder, pipeline: Pipeline):
        serialized_model: bytes = pickle.dumps(pipeline)
        serialized_encoder: bytes = pickle.dumps(label_encoder)
        SQLUtil.save_model(model_name, serialized_encoder, serialized_model)

    @staticmethod
    def load_model(model_name: str):
        model: bytes = SQLUtil.get_model(model_name)
        loaded_model = pickle.loads(model[1])
        label_encoder = pickle.loads(model[2])
        return loaded_model, label_encoder

    @staticmethod
    def get_models_list() -> set[str]:
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
    def get_function(model_name: str, function_name: str) -> list:
        function: list = SQLUtil.get_function(model_name, function_name)
        return function

    @staticmethod
    def add_model_functions(training_request: TrainingRequest):
        functions: list = training_request.get_functions()
        if functions is not None:
            SQLUtil.save_functions(training_request.model_name, functions)

    @staticmethod
    def add_prediction_functions(prediction_request: PredictionRequest, predictions: list[str]):
        functions = prediction_request.get_functions()
        task_name = prediction_request.task_name

        if functions is not None:
            for (ctr, function) in enumerate(functions):
                function["functionName"] = predictions[ctr]
            SQLUtil.save_predictions(
                task_name, prediction_request.model_name, functions)

    @staticmethod
    def get_prediction_function(task_name: str, model_name: str, function_name: str) -> dict:
        prediction_function: dict = SQLUtil.get_prediction_function(
            task_name, model_name, function_name)
        return prediction_function
