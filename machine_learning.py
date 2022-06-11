
import pickle

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline


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
        # need to save to sqlite
        pickle.dump(pipeline, open(model_name, 'wb'))

    @staticmethod
    def load_model(model_name: str) -> Pipeline:
        # need to load from sqlite
        loaded_model = pickle.load(open(model_name, 'rb'))
        return loaded_model
