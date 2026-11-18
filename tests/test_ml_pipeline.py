"""Unit tests for ``app.config.ml_pipeline.MLTask`` (TESTS.md P2).

Covers the shape/params of the multi-class pipeline and a fit/predict
round-trip on tiny synthetic data.
"""

from typing import Any

from app.config.ml_pipeline import MLTask
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline


class TestGetMultiClassPipeline:
    """Pipeline construction, step names, and parameter values."""

    def test_returns_a_pipeline(self) -> None:
        pipeline = MLTask.get_multi_class_pipeline()
        assert isinstance(pipeline, Pipeline)

    def test_pipeline_steps_and_params(self) -> None:
        pipeline = MLTask.get_multi_class_pipeline()
        names = [name for name, _ in pipeline.steps]
        assert names == ["preprocessor", "clf"]

        preprocessor = pipeline.named_steps["preprocessor"]
        assert isinstance(preprocessor, TfidfVectorizer)
        assert preprocessor.ngram_range == (2, 4)
        assert preprocessor.norm == "l2"
        assert preprocessor.sublinear_tf is True

        clf = pipeline.named_steps["clf"]
        assert isinstance(clf, MultinomialNB)
        assert clf.alpha == 1e-8

    def test_calling_twice_returns_independent_instances(self) -> None:
        # A fresh pipeline per call so concurrent tasks never share state.
        a = MLTask.get_multi_class_pipeline()
        b = MLTask.get_multi_class_pipeline()
        assert a is not b
        assert a.named_steps["preprocessor"] is not b.named_steps["preprocessor"]


class TestPipelineFitPredictRoundtrip:
    """fit/predict round-trip on tiny synthetic data."""

    @staticmethod
    def _corpus() -> tuple[list[str], list[str]]:
        # Distinctive n-grams per class so TF-IDF + NB can separate them.
        docs = [
            "alpha beta gamma delta",
            "alpha beta gamma epsilon",
            "alpha beta gamma zeta",
            "omega phi chi psi",
            "omega phi chi sigma",
            "omega phi chi tau",
        ]
        labels = ["a", "a", "a", "b", "b", "b"]
        return docs, labels

    def test_fit_predict_roundtrip(self) -> None:
        docs, labels = self._corpus()
        pipeline = MLTask.get_multi_class_pipeline()
        pipeline.fit(docs, labels)

        predictions = list(pipeline.predict(docs))
        assert predictions == labels

    def test_predict_proba_sums_to_one(self) -> None:
        docs, labels = self._corpus()
        pipeline = MLTask.get_multi_class_pipeline()
        pipeline.fit(docs, labels)

        probas = pipeline.predict_proba(docs)
        assert probas.shape == (len(docs), 2)
        for row in probas:
            assert abs(sum(row) - 1.0) < 1e-6

    def test_unseen_document_still_classifies(self, recwarn: Any) -> None:
        docs, labels = self._corpus()
        pipeline = MLTask.get_multi_class_pipeline()
        pipeline.fit(docs, labels)

        # A document with the "omega phi chi" n-grams should land in class b.
        prediction = pipeline.predict(["omega phi chi psi omega"])
        assert prediction == ["b"]
