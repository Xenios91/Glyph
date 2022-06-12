
import pickle

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline

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
        models_list: list[str] = SQLUtil.get_models_list()
        return models_list
