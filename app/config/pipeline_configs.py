"""ML pipeline configuration utilities."""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline


class MLTask:
    """ML pipeline configuration."""

    @staticmethod
    def get_multi_class_pipeline() -> Pipeline:
        """Get a multi-class classification pipeline.

        Returns:
            A configured sklearn Pipeline with TF-IDF and Naive Bayes.
        """
        return Pipeline(
            [
                ("preprocessor", TfidfVectorizer(ngram_range=(2, 4), norm="l2", sublinear_tf=True)),
                ("clf", MultinomialNB(alpha=1e-8)),
            ]
        )
