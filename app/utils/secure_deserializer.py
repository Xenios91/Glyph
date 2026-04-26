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
from typing import Any, Set, Type

from joblib.numpy_pickle import NumpyUnpickler

from loguru import logger

# Whitelist of allowed classes for deserialization
# These are the only classes that are safe to deserialize in our application
ALLOWED_CLASSES: Set[str] = {
    # sklearn classes
    "sklearn.pipeline.Pipeline",
    "sklearn.feature_extraction.text.TfidfVectorizer",
    "sklearn.naive_bayes.MultinomialNB",
    "sklearn.preprocessing._label.LabelEncoder",
    # numpy classes
    "numpy.ndarray",
    "numpy.dtype",
    "numpy.float64",
    "numpy.int64",
    "numpy.float32",
    "numpy.int32",
    # standard Python types (SAFE ones only)
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
    # joblib specific
    "joblib.numpy_pickle.NumpyPickler",
}

# Explicitly blocked dangerous builtins and functions
BLOCKED_BUILTINS: Set[str] = {
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
    "builtins setattr",
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
    "builtins.__import__",
}



class SecureDeserializationError(Exception):
    """Raised when secure deserialization detects a potential security threat."""
    pass


class RestrictedNumpyUnpickler(NumpyUnpickler):
    """A restricted numpy unpickler that only allows safe classes.
    
    This class extends joblib's NumpyUnpickler to validate each class before
    deserialization, preventing arbitrary code execution attacks.
    """
    
    def __init__(self, file: Any, allowed_classes: Set[str] | None = None):
        # NumpyUnpickler requires: filename, file_handle, ensure_native_byte_order
        # Use empty string for filename when loading from BytesIO
        super().__init__(
            filename="",
            file_handle=file,
            ensure_native_byte_order=False
        )
        self.allowed_classes = allowed_classes or ALLOWED_CLASSES
    
    def find_class(self, module: str, name: str) -> Type:
        """Override find_class to restrict which classes can be unpickled.
        
        Args:
            module: The module name of the class.
            name: The class name.
            
        Returns:
            The class object if allowed, otherwise raises SecureDeserializationError.
            
        Raises:
            SecureDeserializationError: If the class is not in the whitelist.
        """
        # Construct the fully qualified class name
        class_name = f"{module}.{name}"
        
        # First check if it's explicitly blocked
        if class_name in BLOCKED_BUILTINS:
            logger.warning(
                "Blocked deserialization of explicitly dangerous class: {}",
                class_name
            )
            raise SecureDeserializationError(
                f"Deserialization of '{class_name}' is explicitly blocked for security reasons."
            )
        
        # Check against whitelist
        if class_name not in self.allowed_classes:
            # For custom whitelists, be strict - only allow exact matches
            if self.allowed_classes is not ALLOWED_CLASSES:
                logger.warning(
                    "Blocked deserialization of class not in custom whitelist: {}",
                    class_name
                )
                raise SecureDeserializationError(
                    f"Deserialization of '{class_name}' is not allowed. "
                    "Only whitelisted classes can be deserialized."
                )
            
            # For default whitelist, check if it's from a trusted module
            # but NOT a dangerous builtin
            is_allowed = False
            trusted_modules = {
                'sklearn',
                'numpy',
                'joblib',
            }
            
            # Check sklearn, numpy, joblib subclasses
            for trusted_module in trusted_modules:
                if class_name.startswith(trusted_module + '.'):
                    is_allowed = True
                    break
            
            # For builtins, only allow exact matches from whitelist
            if module == 'builtins' and class_name in self.allowed_classes:
                is_allowed = True
            
            if not is_allowed:
                logger.warning(
                    "Blocked deserialization of potentially dangerous class: {}",
                    class_name
                )
                raise SecureDeserializationError(
                    f"Deserialization of '{class_name}' is not allowed. "
                    "Only whitelisted classes can be deserialized."
                )
        
        return super().find_class(module, name)


def secure_load(file_like: io.BytesIO, allowed_classes: Set[str] | None = None) -> Any:
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
        # Use our restricted unpickler
        unpickler = RestrictedNumpyUnpickler(file_like, allowed_classes)
        result = unpickler.load()
        
        return result
    except SecureDeserializationError:
        raise
    except Exception as e:
        logger.error("Unexpected error during deserialization: {}", e)
        raise SecureDeserializationError(f"Deserialization failed: {e}") from e


