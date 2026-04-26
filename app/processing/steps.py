"""Pipeline step implementations for Glyph processing layer.

This module contains concrete implementations of PipelineStep for various
binary analysis tasks including validation, decompilation, tokenization,
filtering, feature extraction, training, and prediction.

Python 3.11+
"""

import os
import re
import sys
from typing import Any, cast

from numpy.typing import NDArray
from sklearn.pipeline import Pipeline as SklearnPipeline

from app.processing.pipeline import PipelineContext, PipelineStep
from app.utils.persistence_util import MLPersistanceUtil, MLTask
from loguru import logger
from app.config.settings import get_settings



# ============================================================================
# Token Filtering Utilities
# ============================================================================

# Patterns for detecting Ghidra auto-named variables
_VARIABLE_PATTERNS = [
    r"^var\d+$",
    r"^local_[0-9a-fA-F]+$",
    r"^[a-z]{1,2}Var\d+$",
    r"^param_\d+$",
    r"^(?:u)?stack_?[-?0-9a-fA-F]+$",
    r"^(?:unaff|extraout)_.*$",
]
_VARIABLE_REGEX = re.compile(f"({'|'.join(_VARIABLE_PATTERNS)})", re.IGNORECASE)


def _check_if_variable(token: str) -> bool:
    """Check if a token matches Ghidra auto-naming patterns.

    Args:
        token: The token to check.

    Returns:
        True if the token matches a Ghidra auto-naming pattern.
    """
    return _VARIABLE_REGEX.match(token) is not None


def _remove_comments(tokens_list: list[str]) -> list[str]:
    """Remove C-style comments from token list.

    Args:
        tokens_list: List of tokens to process.

    Returns:
        List of tokens with comments removed.
    """
    tokens_string: str = " ".join(tokens_list)
    result: str = ""
    i = 0
    while i < len(tokens_string):
        if tokens_string[i : i + 2] == "/*":
            # Found start of comment, look for closing */
            close_idx = tokens_string.find("*/", i + 2)
            if close_idx == -1:
                # Unclosed comment - stop processing
                break
            # Skip past the closed comment
            i = close_idx + 2
        else:
            result += tokens_string[i]
            i += 1
    # Clean up whitespace
    result = " ".join(result.split())
    return result.split() if result else []


def _filter_tokens(tokens_list: list[str]) -> list[str]:
    """Normalize addresses, functions, variables, and undefined types.

    Args:
        tokens_list: List of tokens to filter.

    Returns:
        List of filtered and normalized tokens.
    """
    filtered: list[str] = []
    for token in tokens_list:
        if not token or not token.strip():
            continue

        if "0x" in token:
            filtered.append("HEX")
        elif token.startswith("FUN_"):
            filtered.append("FUNCTION")
        elif _check_if_variable(token):
            filtered.append("VARIABLE")
        elif re.match(r"^undefined\d+$", token):
            filtered.append("undefined")
        else:
            filtered.append(token)

    return _remove_comments(filtered)


# ============================================================================
# Pipeline Step Implementations
# ============================================================================


class ValidationStep(PipelineStep):
    """Validates that a binary file exists and is readable.

    This step performs basic validation checks on the binary file:
    - File exists
    - File is readable
    - File size is within acceptable limits
    """

    def __init__(self, max_size_mb: float = 100.0) -> None:
        """Initialize the validation step.

        Args:
            max_size_mb: Maximum allowed file size in megabytes.
        """
        self._max_size_bytes = int(max_size_mb * 1024 * 1024)

    def get_name(self) -> str:
        """Return the name of this step."""
        return "ValidationStep"

    def execute(self, context: PipelineContext) -> PipelineContext:
        """Validate the binary file.

        Args:
            context: The pipeline context.

        Returns:
            Updated context with validation results.
        """
        binary_path = context.binary_path

        # Check file exists
        if not os.path.exists(binary_path):
            context.error = f"Binary file not found: {binary_path}"
            return context

        # Check file is readable
        if not os.access(binary_path, os.R_OK):
            context.error = f"Binary file not readable: {binary_path}"
            return context

        # Check file size
        file_size = os.path.getsize(binary_path)
        if file_size > self._max_size_bytes:
            context.error = (
                f"Binary file exceeds maximum size: {file_size} > "
                f"{self._max_size_bytes} bytes"
            )
            return context

        # Check file is not empty
        if file_size == 0:
            context.error = f"Binary file is empty: {binary_path}"
            return context

        logger.debug("Validation passed for {} ({} bytes)", binary_path, file_size)
        return context


class DecompileStep(PipelineStep):
    """Runs Ghidra decompilation on the binary.

    This step uses the ghidra_processor module to analyze and decompile
    the binary, extracting function information.
    """

    def __init__(self) -> None:
        """Initialize the decompile step."""
    def get_name(self) -> str:
        """Return the name of this step."""
        return "DecompileStep"

    def execute(self, context: PipelineContext) -> PipelineContext:
        """Decompile the binary using Ghidra.

        Args:
            context: The pipeline context.

        Returns:
            Updated context with decompiled functions.
        """
        from app.processing import ghidra_processor

        binary_path = context.binary_path

        try:
            results = ghidra_processor.analyze_binary_and_decompile(binary_path)

            functions = results.get("functions", [])
            errored_functions = results.get("erroredFunctions", [])

            context.set("functions", functions)
            context.set("errored_functions", errored_functions)

            logger.info(
                "Decompilation completed: {} functions, {} errors",
                len(functions),
                len(errored_functions))

        except Exception as decompile_error:
            context.error = f"Decompilation failed: {decompile_error}"
            context.exc_info = sys.exc_info()
            logger.error(
                "Decompilation error: {}", decompile_error)

        return context


class TokenizeStep(PipelineStep):
    """Extracts tokens from decompiled functions.

    This step processes the decompiled functions and extracts token lists,
    joining them into strings for further processing.
    """

    def __init__(self) -> None:
        """Initialize the tokenize step."""
    def get_name(self) -> str:
        """Return the name of this step."""
        return "TokenizeStep"

    def execute(self, context: PipelineContext) -> PipelineContext:
        """Extract tokens from decompiled functions.

        Args:
            context: The pipeline context.

        Returns:
            Updated context with tokenized functions.
        """
        functions = context.get("functions")
        if functions is None:
            context.error = (
                "No functions found in context - decompilation may have failed"
            )
            return context

        tokenized_functions: list[dict[str, Any]] = []
        for function in functions:
            token_list = function.get("tokenList", [])
            if token_list:
                tokens = " ".join(token_list)
                function_copy = function.copy()
                function_copy["tokens"] = tokens
                tokenized_functions.append(function_copy)

        context.set("tokenized_functions", tokenized_functions)

        logger.debug(
            "Tokenization completed: {} functions tokenized", len(tokenized_functions)
        )

        return context


class FilterStep(PipelineStep):
    """Filters and normalizes tokens from decompiled code.

    This step applies token filtering to normalize addresses, function names,
    variable names, and remove comments.
    """

    def __init__(self) -> None:
        """Initialize the filter step."""
    def get_name(self) -> str:
        """Return the name of this step."""
        return "FilterStep"

    def execute(self, context: PipelineContext) -> PipelineContext:
        """Filter and normalize tokens.

        Args:
            context: The pipeline context.

        Returns:
            Updated context with filtered tokens.
        """
        tokenized_functions = context.get("tokenized_functions")
        if tokenized_functions is None:
            context.error = "No tokenized functions found in context"
            return context

        filtered_functions: list[dict[str, Any]] = []
        for function in tokenized_functions:
            token_list = function.get("tokenList", [])
            if token_list:
                filtered_tokens = _filter_tokens(token_list)
                tokens = " ".join(filtered_tokens)
                function_copy = function.copy()
                function_copy["tokenList"] = filtered_tokens
                function_copy["tokens"] = tokens
                filtered_functions.append(function_copy)

        context.set("filtered_functions", filtered_functions)

        logger.debug(
            "Filtering completed: {} functions filtered", len(filtered_functions)
        )

        return context


class FeatureExtractStep(PipelineStep):
    """Extracts tokens from filtered functions for ML pipeline.

    This step extracts token sequences from filtered functions and stores
    them in the context for the ML pipeline to transform during training/prediction.
    The actual TF-IDF vectorization is handled by the ML pipeline's internal
    TfidfVectorizer to avoid redundant transformations.
    """

    def __init__(self) -> None:
        """Initialize the feature extraction step."""
    def get_name(self) -> str:
        """Return the name of this step."""
        return "FeatureExtractStep"

    def execute(self, context: PipelineContext) -> PipelineContext:
        """Extract tokens from filtered functions.

        Args:
            context: The pipeline context.

        Returns:
            Updated context with extracted tokens.
        """
        filtered_functions = context.get("filtered_functions")
        if filtered_functions is None:
            context.error = "No filtered functions found in context"
            return context

        # Extract tokens from functions
        tokens = [f.get("tokens", "") for f in filtered_functions if f.get("tokens")]

        if not tokens:
            context.error = "No tokens found for feature extraction"
            return context

        # Store tokens for the ML pipeline to transform
        # The ML pipeline includes its own TfidfVectorizer which will handle
        # the fit_transform operation during training
        context.set("tokens", tokens)

        logger.debug(
            "Feature extraction completed: {} samples",
            len(tokens))

        return context


class TrainStep(PipelineStep):
    """Trains a machine learning model.

    This step trains an ML model using the extracted features and saves
    the trained model to persistence.
    """

    def __init__(self) -> None:
        """Initialize the train step."""
    def get_name(self) -> str:
        """Return the name of this step."""
        return "TrainStep"

    def execute(self, context: PipelineContext) -> PipelineContext:
        """Train the ML model.

        Args:
            context: The pipeline context.

        Returns:
            Updated context with training results.
        """
        import numpy as np
        from sklearn import preprocessing

        # Get required data
        filtered_functions = context.get("filtered_functions")
        tokens = context.get("tokens")

        if filtered_functions is None:
            context.error = "No filtered functions found in context"
            return context

        if tokens is None:
            context.error = "No tokens found in context"
            return context

        model_name = context.metadata.get("model_name")
        if model_name is None:
            context.error = "model_name not found in context metadata"
            return context

        # Extract labels (function names)
        labels = [f.get("functionName", "Unknown") for f in filtered_functions]

        # Encode labels
        label_encoder = preprocessing.LabelEncoder()
        y = cast(NDArray, label_encoder.fit_transform(labels))
        


        # Get ML pipeline
        ml_pipeline: SklearnPipeline = MLTask.get_multi_class_pipeline()

        try:
            # Validate data before training
            logger.debug("Training data: {} tokens, {} labels", len(tokens), len(y))
            # Guard expensive debug logging to avoid computation when disabled
            # Using opt(lazy=True) defers evaluation until the log level is confirmed
            logger.opt(lazy=True).debug("Token sample: {}", lambda: tokens[0][:100] if tokens else "empty")
            logger.opt(lazy=True).debug("Label distribution: {}", np.bincount)
            
            # Train the model - ML pipeline handles vectorization internally
            ml_pipeline.fit(tokens, y)

            # Save the model
            MLPersistanceUtil.save_model(model_name, label_encoder, ml_pipeline)

            context.set("label_encoder", label_encoder)
            context.set("model", ml_pipeline)

            logger.info(
                "Training completed for model '{}': {} classes",
                model_name,
                len(label_encoder.classes_))

        except Exception as train_error:
            context.error = f"Training failed: {train_error}"
            context.exc_info = sys.exc_info()
            logger.error("Training error: {}", train_error)
        return context


class PredictStep(PipelineStep):
    """Runs predictions using a trained model.

    This step loads a trained model and runs predictions on the extracted
    features, applying a probability threshold to filter uncertain predictions.
    """

    def __init__(self) -> None:
        """Initialize the predict step."""
    def get_name(self) -> str:
        """Return the name of this step."""
        return "PredictStep"

    def execute(self, context: PipelineContext) -> PipelineContext:
        """Run predictions on the features.

        Args:
            context: The pipeline context.

        Returns:
            Updated context with predictions.
        """
        # Get required data
        filtered_functions = context.get("filtered_functions")
        tokens = context.get("tokens")
        model_name = context.metadata.get("model_name")

        if filtered_functions is None:
            context.error = "No filtered functions found in context"
            return context

        if tokens is None:
            context.error = "No tokens found in context"
            return context

        if model_name is None:
            context.error = "model_name not found in context metadata"
            return context

        try:
            # Load the model
            model, label_encoder = MLPersistanceUtil.load_model(model_name)

            # Run predictions - ML pipeline handles vectorization internally
            predictions = model.predict(tokens)
            prediction_probability = model.predict_proba(tokens) * 100
            predicted_labels = label_encoder.inverse_transform(predictions)

            # Apply probability threshold
            settings = get_settings()
            threshold = settings.prediction_probability_threshold
            for ctr, probability in enumerate(prediction_probability):
                if probability.max() < threshold:
                    predicted_labels[ctr] = "Unknown"

            context.set("predictions", predicted_labels.tolist())
            context.set("prediction_probabilities", prediction_probability.tolist())

            logger.info(
                "Prediction completed: {} predictions for model '{}'",
                len(predicted_labels),
                model_name)

        except Exception as predict_error:
            context.error = f"Prediction failed: {predict_error}"
            context.exc_info = sys.exc_info()
            logger.error("Prediction error: {}", predict_error)

        return context
