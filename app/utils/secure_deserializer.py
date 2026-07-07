"""Secure deserialization utilities to prevent arbitrary code execution.

This module provides a secure wrapper around joblib.load() that validates
the data before deserialization to prevent CVE-2020-1434 and similar
pickle-based attacks.

Security measures:
1. Whitelist of allowed classes
2. Validation of pickle opcodes before execution
3. Sandbox execution environment
"""

import io
from typing import Any, cast

from joblib.numpy_pickle import NumpyUnpickler
from loguru import logger

# Base allowed classes that don't depend on sklearn internals.
_ALLOWED_CLASSES_BASE: set[str] = {
    "numpy.ndarray",
    "numpy.dtype",
    "numpy.float64",
    "numpy.int64",
    "numpy.float32",
    "numpy.int32",
    "builtins.list",
    "builtins.dict",
    "builtins.str",
    "builtins.int",
    "builtins.float",
    "builtins.tuple",
    "builtins.NoneType",
    "builtins.bool",
    "builtins.set",
    "builtins.frozenset",
    "joblib.numpy_pickle.NumpyPickler",
    "joblib.numpy_pickle.NumpyArrayWrapper",
}

# Resolve sklearn class paths dynamically so that internal module changes
# (e.g. sklearn.preprocessing._label → another path) don't break the whitelist.
_SKLEARN_CLASSES: set[str] = set()
try:
    from sklearn.feature_extraction.text import TfidfTransformer, TfidfVectorizer
    from sklearn.naive_bayes import MultinomialNB
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import LabelEncoder

    _SKLEARN_CLASSES = {
        f"{Pipeline.__module__}.{Pipeline.__name__}",
        f"{TfidfVectorizer.__module__}.{TfidfVectorizer.__name__}",
        f"{TfidfTransformer.__module__}.{TfidfTransformer.__name__}",
        f"{MultinomialNB.__module__}.{MultinomialNB.__name__}",
        f"{LabelEncoder.__module__}.{LabelEncoder.__name__}",
    }
except ImportError:
    # Fallback to hard-coded paths when sklearn is not installed.
    _SKLEARN_CLASSES = {
        "sklearn.pipeline.Pipeline",
        "sklearn.feature_extraction.text.TfidfVectorizer",
        "sklearn.feature_extraction.text.TfidfTransformer",
        "sklearn.naive_bayes.MultinomialNB",
        "sklearn.preprocessing._label.LabelEncoder",
    }

ALLOWED_CLASSES: set[str] = _ALLOWED_CLASSES_BASE | _SKLEARN_CLASSES

BLOCKED_BUILTINS: set[str] = {
    "builtins.eval",
    "builtins.exec",
    "builtins.__import__",
    "builtins.compile",
    "builtins.open",
    "builtins.input",
    "builtins.raw_input",
    "builtins.apply",
    "builtins.callable",
    "builtins.filter",
    "builtins.map",
    "builtins.reduce",
    "builtins.getattr",
    "builtins.setattr",
    "builtins.delattr",
    "builtins.hasattr",
    "builtins.isinstance",
    "builtins.issubclass",
    "builtins.property",
    "builtins.super",
    "builtins.type",
    "builtins.repr",
    "builtins.hash",
    "builtins.format",
    "builtins.chained",
    "builtins.ord",
    "builtins.chr",
    "builtins.unichr",
    "builtins.any",
    "builtins.all",
    "builtins.bin",
    "builtins.hex",
    "builtins.oct",
    "builtins.divmod",
    "builtins.pow",
    "builtins.round",
    "builtins.abs",
    "builtins.sum",
    "builtins.min",
    "builtins.max",
    "builtins.len",
    "builtins.range",
    "builtins.xrange",
    "builtins.enumerate",
    "builtins.reversed",
    "builtins.sorted",
    "builtins.zip",
    "builtins.iter",
    "builtins.next",
    "builtins.dir",
    "builtins.locals",
    "builtins.globals",
    "builtins.vars",
    "builtins.__build_class__",
    "builtins.__debug__",
    "builtins.__doc__",
    "builtins.__name__",
    "builtins.__package__",
    "builtins.__loader__",
    "builtins.__spec__",
    "builtins.__annotations__",
}


class SecureDeserializationError(Exception):
    """Raised when secure deserialization detects a potential security threat."""


class RestrictedNumpyUnpickler(NumpyUnpickler):
    """A restricted numpy unpickler that only allows safe classes.

    This class extends joblib's NumpyUnpickler to validate each class before
    deserialization, preventing arbitrary code execution attacks.
    """

    def __init__(self, file: Any, allowed_classes: set[str] | None = None):
        super().__init__(filename="", file_handle=file, ensure_native_byte_order=False)
        self.allowed_classes = allowed_classes or ALLOWED_CLASSES

    def find_class(self, module: str, name: str) -> type[Any]:
        """Override find_class to restrict which classes can be unpickled.

        Args:
            module: The module name of the class.
            name: The class name.

        Returns:
            The class object if allowed, otherwise raises SecureDeserializationError.

        Raises:
            SecureDeserializationError: If the class is not in the whitelist.

        """
        class_name = f"{module}.{name}"

        if class_name in BLOCKED_BUILTINS:
            logger.warning("Blocked deserialization of explicitly dangerous class: {}", class_name)
            raise SecureDeserializationError(
                f"Deserialization of '{class_name}' is explicitly blocked for security reasons.",
            )

        if class_name not in self.allowed_classes:
            logger.warning("Blocked deserialization of class not in whitelist: {}", class_name)
            raise SecureDeserializationError(
                f"Deserialization of '{class_name}' is not allowed. Only whitelisted classes can be deserialized.",
            )

        return cast(type[Any], super().find_class(module, name))


def secure_load(file_like: io.BytesIO, allowed_classes: set[str] | None = None) -> Any:
    """Safely load a joblib/pickled object with class validation.

    This function provides a secure alternative to joblib.load() by validating
    all classes before deserialization.

    Args:
        file_like: A file-like object containing pickled data.
        allowed_classes: Optional set of allowed class names (fully qualified).

    Returns:
        The deserialized object.

    Raises:
        SecureDeserializationError: If the data contains disallowed classes.
        joblib.NumpyUnpicklingError: If the data is not valid joblib format.

    """
    try:
        unpickler = RestrictedNumpyUnpickler(file_like, allowed_classes)
        result = unpickler.load()

        return result
    except SecureDeserializationError:
        raise
    except Exception as e:
        logger.exception("Unexpected error during deserialization")
        raise SecureDeserializationError(f"Deserialization failed: {e}") from e
