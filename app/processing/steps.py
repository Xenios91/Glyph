"""Pipeline step implementations for Glyph processing layer.

This module contains concrete implementations of PipelineStep for various
binary analysis tasks including validation, decompilation, tokenization,
filtering, feature extraction, training, and prediction.

Python 3.11+
"""

import asyncio
import io
import joblib
import os
import re
import sys
from typing import Any, cast

from loguru import logger
from numpy import int64
from numpy.typing import NDArray
from sklearn.pipeline import Pipeline as SklearnPipeline

from app.config.pipeline_configs import MLTask
from app.config.settings import get_settings
from app.database.model_repository import ModelRepository
from app.processing.pipeline import PipelineContext, PipelineStep

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
            close_idx = tokens_string.find("*/", i + 2)
            if close_idx == -1:
                break
            i = close_idx + 2
        else:
            result += tokens_string[i]
            i += 1
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

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """Validate the binary file.

        Args:
            context: The pipeline context.

        Returns:
            Updated context with validation results.

        """
        binary_path = context.binary_path

        if not os.path.exists(binary_path):
            context.error = f"Binary file not found: {binary_path}"
            return context

        if not os.access(binary_path, os.R_OK):
            context.error = f"Binary file not readable: {binary_path}"
            return context

        file_size = os.path.getsize(binary_path)
        if file_size > self._max_size_bytes:
            context.error = f"Binary file exceeds maximum size: {file_size} > {self._max_size_bytes} bytes"
            return context

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

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """Decompile the binary using Ghidra.

        Args:
            context: The pipeline context.

        Returns:
            Updated context with decompiled functions.

        """
        from app.processing import ghidra_processor

        binary_path = context.binary_path

        try:
            results = await asyncio.to_thread(ghidra_processor.analyze_binary_and_decompile, binary_path)

            functions = results.get("functions", [])
            errored_functions = results.get("erroredFunctions", [])

            context.set("functions", functions)
            context.set("errored_functions", errored_functions)

            logger.info("Decompilation completed: {} functions, {} errors", len(functions), len(errored_functions))

        except Exception as decompile_error:
            context.error = f"Decompilation failed: {decompile_error}"
            context.exc_info = sys.exc_info()
            logger.exception("Decompilation error")

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

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """Extract tokens from decompiled functions.

        Args:
            context: The pipeline context.

        Returns:
            Updated context with tokenized functions.

        """
        functions = context.get("functions")
        if functions is None:
            context.error = "No functions found in context - decompilation may have failed"
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

        logger.debug("Tokenization completed: {} functions tokenized", len(tokenized_functions))

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

    async def execute(self, context: PipelineContext) -> PipelineContext:
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

        logger.debug("Filtering completed: {} functions filtered", len(filtered_functions))

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

    async def execute(self, context: PipelineContext) -> PipelineContext:
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

        tokens = [f.get("tokens", "") for f in filtered_functions if f.get("tokens")]

        if not tokens:
            context.error = "No tokens found for feature extraction"
            return context

        context.set("tokens", tokens)

        logger.debug("Feature extraction completed: {} samples", len(tokens))

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

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """Train the ML model.

        Args:
            context: The pipeline context.

        Returns:
            Updated context with training results.

        """
        import numpy as np
        from sklearn import preprocessing

        filtered_functions = context.get("filtered_functions")
        tokens = context.get("tokens")

        if not filtered_functions:
            context.error = "No filtered functions available for training"
            return context

        if tokens is None:
            context.error = "No tokens found in context"
            return context

        model_name = context.metadata.get("model_name")
        if model_name is None:
            context.error = "model_name not found in context metadata"
            return context

        labels = [f.get("functionName", "Unknown") for f in filtered_functions]

        label_encoder = preprocessing.LabelEncoder()
        y: NDArray[int64] = cast(
            NDArray[int64],
            label_encoder.fit_transform(labels),
        )

        ml_pipeline: SklearnPipeline = MLTask.get_multi_class_pipeline()

        try:
            logger.debug("Training data: {} tokens, {} labels", len(tokens), len(y))
            logger.opt(lazy=True).debug("Token sample: {}", lambda: tokens[0][:100] if tokens else "empty")
            logger.opt(lazy=True).debug("Label distribution: {}", lambda: np.bincount(y).tolist())

            await asyncio.to_thread(ml_pipeline.fit, tokens, y)

            # Serialize to bytes before saving to database
            encoder_buffer = io.BytesIO()
            joblib.dump(label_encoder, encoder_buffer)
            model_buffer = io.BytesIO()
            joblib.dump(ml_pipeline, model_buffer)

            await ModelRepository.save(  # type: ignore[attr-defined]
                model_name, encoder_buffer.getvalue(), model_buffer.getvalue()
            )

            context.set("label_encoder", label_encoder)
            context.set("model", ml_pipeline)

            logger.info(
                "Training completed for model '{}': {} classes",
                model_name,
                len(label_encoder.classes_),
            )

        except Exception as train_error:
            context.error = f"Training failed: {train_error}"
            context.exc_info = sys.exc_info()
            logger.exception("Training error")
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

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """Run predictions on the features.

        Args:
            context: The pipeline context.

        Returns:
            Updated context with predictions.

        """
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
            model, label_encoder = await ModelRepository.load_model(model_name)  # type: ignore[attr-defined]

            predictions = await asyncio.to_thread(model.predict, tokens)
            prediction_probability = await asyncio.to_thread(model.predict_proba, tokens)
            prediction_probability = prediction_probability * 100
            predicted_labels = label_encoder.inverse_transform(predictions)

            settings = get_settings()
            threshold = settings.prediction_probability_threshold

            # Validate that prediction_probability shape matches tokens.
            if len(prediction_probability) != len(tokens):
                context.error = (
                    f"Prediction probability array shape mismatch: "
                    f"got {len(prediction_probability)} rows, expected {len(tokens)}"
                )
                logger.warning(
                    "Prediction probability shape mismatch: %d rows vs %d tokens",
                    len(prediction_probability),
                    len(tokens),
                )
                return context

            for ctr, probability in enumerate(prediction_probability):
                if probability.max() < threshold:
                    predicted_labels[ctr] = "Unknown"

            context.set("predictions", predicted_labels.tolist())
            context.set("prediction_probabilities", prediction_probability.tolist())

            logger.info("Prediction completed: {} predictions for model '{}'", len(predicted_labels), model_name)

        except Exception as predict_error:
            context.error = f"Prediction failed: {predict_error}"
            context.exc_info = sys.exc_info()
            logger.exception("Prediction error")

        return context


class SaveRawFunctionsStep(PipelineStep):
    """Save raw decompiled functions to the BinaryFunction database table.

    Called after DecompileStep in the upload pipeline. Stores the raw
    C code output from Ghidra without any tokenization or filtering.
    """

    def __init__(self) -> None:
        """Initialize the save raw functions step."""

    def get_name(self) -> str:
        """Return the name of this step."""
        return "SaveRawFunctionsStep"

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """Save raw decompiled functions to the database.

        Expects the context to have:
            - binary_id: The parent binary primary key
            - functions: List of function dicts from DecompileStep
                       (each must contain functionName, lowAddress, raw_code)

        Args:
            context: The pipeline context.

        Returns:
            Updated context with save confirmation.

        """
        from app.database.sql_service import SQLUtil

        binary_id = context.get("binary_id")
        functions = context.get("functions")

        if binary_id is None:
            context.error = "Missing binary_id in context"
            return context

        if not functions:
            logger.warning("No functions to save for binary {}", binary_id)
            context.set("functions_saved", 0)
            return context

        db_functions: list[dict[str, Any]] = []
        for func in functions:
            raw_code = func.get("raw_code", "")
            if not raw_code:
                continue
            db_functions.append(
                {
                    "function_name": func.get("functionName", "unknown"),
                    "entrypoint": func.get("lowAddress", "0"),
                    "raw_code": raw_code,
                },
            )

        if db_functions:
            await SQLUtil.save_binary_functions(binary_id, db_functions)
            logger.info("Saved {} raw functions for binary {}", len(db_functions), binary_id)

        context.set("functions_saved", len(db_functions))
        return context


class LoadBinaryFunctionsStep(PipelineStep):
    """Load raw functions from the BinaryFunction table for a given binary.

    Used at the start of task pipelines (ML Training, ML Prediction,
    Code Reuse) to load stored raw functions instead of re-decompiling.
    """

    def __init__(self) -> None:
        """Initialize the load binary functions step."""

    def get_name(self) -> str:
        """Return the name of this step."""
        return "LoadBinaryFunctionsStep"

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """Load raw functions for the binary specified in context.

        Expects the context to have:
            - binary_id: The parent binary primary key

        Sets in context:
            - functions: List of function dicts ready for TokenizeStep

        Args:
            context: The pipeline context.

        Returns:
            Updated context with loaded functions.

        """
        from app.database.sql_service import SQLUtil

        binary_id = context.get("binary_id")
        if binary_id is None:
            context.error = "Missing binary_id in context"
            return context

        try:
            binary_functions = await SQLUtil.get_binary_functions(binary_id)

            if not binary_functions:
                context.error = f"No functions found for binary {binary_id}"
                return context

            # Convert BinaryFunction ORM objects to the dict format
            # expected by TokenizeStep (matching Ghidra output structure)
            functions: list[dict[str, Any]] = []
            for bf in binary_functions:
                # Split raw_code back into token-like list for TokenizeStep
                # The TokenizeStep reads func.get("tokenList", [])
                functions.append(
                    {
                        "functionName": bf.function_name,
                        "lowAddress": bf.entrypoint,
                        "tokenList": bf.raw_code.split(),  # Space-separated tokens
                        "raw_code": bf.raw_code,
                    },
                )

            context.set("functions", functions)
            logger.info("Loaded {} functions for binary {}", len(functions), binary_id)

        except Exception:
            context.error = f"Failed to load functions for binary {binary_id}"
            context.exc_info = sys.exc_info()
            logger.exception("Error loading binary functions")

        return context
