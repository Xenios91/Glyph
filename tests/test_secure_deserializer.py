"""Unit tests for secure deserialization module.

These tests verify that the secure deserializer:
1. Successfully loads valid sklearn/numpy objects
2. Blocks malicious pickle payloads
3. Handles edge cases correctly
"""

import pickle
from io import BytesIO

import joblib
import numpy as np
import pytest
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer

from app.utils.secure_deserializer import (
    secure_load,
    SecureDeserializationError,
    RestrictedNumpyUnpickler,
    BLOCKED_BUILTINS,
)


class TestSecureLoad:
    """Tests for the secure_load function."""

    def test_load_valid_sklearn_pipeline(self) -> None:
        """Test that valid sklearn pipelines can be loaded."""
        # Create a valid pipeline
        pipeline = Pipeline([
            ('tfidf', TfidfVectorizer(ngram_range=(2, 4))),
            ('clf', MultinomialNB())
        ])

        # Serialize it
        buffer = BytesIO()
        joblib.dump(pipeline, buffer)  # pyright: ignore[reportUnknownMemberType]
        buffer.seek(0)

        # Load it securely
        loaded = secure_load(buffer)

        assert isinstance(loaded, Pipeline)
        assert len(loaded.steps) == 2  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]

    def test_load_valid_numpy_array(self) -> None:
        """Test that valid numpy arrays can be loaded."""
        # Create a valid numpy array
        arr = np.array([1, 2, 3, 4, 5])

        # Serialize it
        buffer = BytesIO()
        joblib.dump(arr, buffer)  # pyright: ignore[reportUnknownMemberType]
        buffer.seek(0)

        # Load it securely
        loaded = secure_load(buffer)

        assert isinstance(loaded, np.ndarray)
        assert np.array_equal(loaded, arr)  # pyright: ignore[reportUnknownArgumentType]

    def test_load_valid_list(self) -> None:
        """Test that valid Python lists can be loaded."""
        # Create a valid list
        data = [{'functionName': 'test', 'tokens': 'abc'}]

        # Serialize it
        buffer = BytesIO()
        joblib.dump(data, buffer)  # pyright: ignore[reportUnknownMemberType]
        buffer.seek(0)

        # Load it securely
        loaded = secure_load(buffer)

        assert isinstance(loaded, list)
        assert len(loaded) == 1  # pyright: ignore[reportUnknownArgumentType]
        assert loaded[0]['functionName'] == 'test'

    def test_load_valid_dict(self) -> None:
        """Test that valid Python dicts can be loaded."""
        # Create a valid dict
        data = {'key': 'value', 'number': 42}

        # Serialize it
        buffer = BytesIO()
        joblib.dump(data, buffer)  # pyright: ignore[reportUnknownMemberType]
        buffer.seek(0)

        # Load it securely
        loaded = secure_load(buffer)

        assert isinstance(loaded, dict)
        assert loaded['key'] == 'value'
        assert loaded['number'] == 42

    def test_load_valid_label_encoder(self) -> None:
        """Test that valid sklearn LabelEncoder can be loaded."""
        from sklearn.preprocessing import LabelEncoder

        # Create and fit a label encoder
        le = LabelEncoder()
        le.fit(['cat', 'dog', 'bird'])  # pyright: ignore[reportUnknownMemberType]

        # Serialize it
        buffer = BytesIO()
        joblib.dump(le, buffer)  # pyright: ignore[reportUnknownMemberType]
        buffer.seek(0)

        # Load it securely
        loaded = secure_load(buffer)

        assert isinstance(loaded, LabelEncoder)
        assert len(loaded.classes_) == 3  # pyright: ignore[reportUnknownMemberType, reportArgumentType]


class TestMaliciousPayloadBlocking:
    """Tests that verify malicious payloads are blocked."""

    def test_block_subprocess_import(self):
        """Test that pickle payloads with subprocess are blocked."""
        # Create a malicious pickle that tries to import subprocess
        class MaliciousSubprocess:
            def __reduce__(self):
                import subprocess
                return (subprocess.call, (['echo', 'pwned'],))

        buffer = BytesIO()
        pickle.dump(MaliciousSubprocess(), buffer)
        buffer.seek(0)

        # This should raise SecureDeserializationError
        with pytest.raises(SecureDeserializationError) as exc_info:
            secure_load(buffer)

        assert "not allowed" in str(exc_info.value).lower() or "security" in str(exc_info.value).lower()

    def test_block_os_system(self):
        """Test that pickle payloads with os.system are blocked."""
        class MaliciousOS:
            def __reduce__(self):
                import os
                return (os.system, ('echo pwned',))

        buffer = BytesIO()
        pickle.dump(MaliciousOS(), buffer)
        buffer.seek(0)

        # This should raise SecureDeserializationError
        with pytest.raises(SecureDeserializationError) as exc_info:
            secure_load(buffer)

        assert "not allowed" in str(exc_info.value).lower() or "security" in str(exc_info.value).lower()

    def test_block_eval(self):
        """Test that pickle payloads with eval are blocked."""
        # Verify eval is in the blocked list
        assert "builtins.eval" in BLOCKED_BUILTINS

        # Test that find_class blocks eval directly
        buffer = BytesIO()
        unpickler = RestrictedNumpyUnpickler(buffer)

        # This should raise SecureDeserializationError
        with pytest.raises(SecureDeserializationError) as exc_info:
            unpickler.find_class('builtins', 'eval')

        assert "blocked" in str(exc_info.value).lower()

    def test_block_exec(self):
        """Test that pickle payloads with exec are blocked."""
        # Verify exec is in the blocked list
        assert "builtins.exec" in BLOCKED_BUILTINS

        # Test that find_class blocks exec directly
        buffer = BytesIO()
        unpickler = RestrictedNumpyUnpickler(buffer)

        # This should raise SecureDeserializationError
        with pytest.raises(SecureDeserializationError) as exc_info:
            unpickler.find_class('builtins', 'exec')

        assert "blocked" in str(exc_info.value).lower()

    def test_block_arbitrary_class(self):
        """Test that arbitrary classes not in whitelist are blocked."""
        # Test that find_class blocks classes from non-whitelisted modules
        buffer = BytesIO()
        unpickler = RestrictedNumpyUnpickler(buffer)

        # This should raise SecureDeserializationError because malicious_module
        # is not in the whitelist
        with pytest.raises(SecureDeserializationError) as exc_info:
            unpickler.find_class('malicious_module', 'EvilClass')

        assert "not allowed" in str(exc_info.value).lower()


class TestRestrictedNumpyUnpickler:
    """Tests for the RestrictedNumpyUnpickler class."""

    def test_find_class_allowed(self):
        """Test that allowed classes can be found."""
        buffer = BytesIO()
        unpickler = RestrictedNumpyUnpickler(buffer)

        # Test builtins specifically
        cls = unpickler.find_class('builtins', 'list')
        assert cls is list

    def test_find_class_custom_whitelist(self):
        """Test that custom whitelist is respected."""
        buffer = BytesIO()
        custom_whitelist = {'builtins.list'}
        unpickler = RestrictedNumpyUnpickler(buffer, custom_whitelist)

        # This should work
        cls = unpickler.find_class('builtins', 'list')
        assert cls is list

        # This should fail
        with pytest.raises(SecureDeserializationError):
            unpickler.find_class('builtins', 'dict')


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_buffer(self):
        """Test handling of empty buffer."""
        buffer = BytesIO()

        with pytest.raises(SecureDeserializationError):
            secure_load(buffer)

    def test_corrupted_data(self):
        """Test handling of corrupted data."""
        buffer = BytesIO(b'not valid pickle data')

        with pytest.raises(SecureDeserializationError):
            secure_load(buffer)

    def test_none_allowed_classes(self) -> None:
        """Test that None allowed_classes uses default whitelist."""
        pipeline = Pipeline([
            ('tfidf', TfidfVectorizer()),
            ('clf', MultinomialNB())
        ])

        buffer = BytesIO()
        joblib.dump(pipeline, buffer)  # pyright: ignore[reportUnknownMemberType]
        buffer.seek(0)

        # Should work with default whitelist
        loaded = secure_load(buffer, allowed_classes=None)
        assert isinstance(loaded, Pipeline)

    def test_custom_allowed_classes(self) -> None:
        """Test that custom allowed_classes is used."""
        data = [1, 2, 3]

        buffer = BytesIO()
        joblib.dump(data, buffer)  # pyright: ignore[reportUnknownMemberType]
        buffer.seek(0)

        # Should work with custom whitelist
        custom_whitelist = {'builtins.list', 'builtins.int'}
        loaded = secure_load(buffer, allowed_classes=custom_whitelist)
        assert loaded == [1, 2, 3]
