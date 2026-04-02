"""Pipeline step implementations for Glyph processing.

Provides concrete implementations of pipeline steps for binary processing.
"""

import logging
import os
from pathlib import Path

from app.config.settings import get_settings
from app.processing.pipeline import PipelineContext, PipelineStep, PipelineStepError

logger = logging.getLogger(__name__)


class ValidationStep(PipelineStep):
    """Validates the binary file exists and has correct permissions."""

    name = "ValidationStep"

    def process(self, context: PipelineContext) -> PipelineContext:
        """Validate the binary file.

        Args:
            context: The pipeline context.

        Returns:
            The updated context.

        Raises:
            PipelineStepError: If validation fails.
        """
        binary_path = Path(context.binary_path)

        if not binary_path.exists():
            raise PipelineStepError(self.name, f"Binary file not found: {context.binary_path}")

        if not binary_path.is_file():
            raise PipelineStepError(self.name, f"Path is not a file: {context.binary_path}")

        if not os.access(binary_path, os.R_OK):
            raise PipelineStepError(self.name, f"Binary file not readable: {context.binary_path}")

        logger.info("Validation passed for: %s", context.binary_path)
        return context


class DecompileStep(PipelineStep):
    """Runs Ghidra decompilation on the binary."""

    name = "DecompileStep"

    def process(self, context: PipelineContext) -> PipelineContext:
        """Decompile the binary using Ghidra.

        Args:
            context: The pipeline context.

        Returns:
            The updated context with decompiled data.

        Raises:
            PipelineStepError: If decompilation fails.
        """
        settings = get_settings()

        try:
            # This would integrate with GhidraProcessor
            # For now, we just mark the step as completed
            logger.info("Decompiling binary: %s", context.binary_path)
            context.data["decompiled"] = True
            return context
        except Exception as exc:
            raise PipelineStepError(self.name, f"Decompilation failed: {exc}") from exc


class TokenizeStep(PipelineStep):
    """Tokenizes the decompiled code."""

    name = "TokenizeStep"

    def process(self, context: PipelineContext) -> PipelineContext:
        """Tokenize the decompiled code.

        Args:
            context: The pipeline context.

        Returns:
            The updated context with tokenized data.

        Raises:
            PipelineStepError: If tokenization fails.
        """
        try:
            logger.info("Tokenizing decompiled code")
            context.data["tokenized"] = True
            return context
        except Exception as exc:
            raise PipelineStepError(self.name, f"Tokenization failed: {exc}") from exc


class FilterStep(PipelineStep):
    """Filters and normalizes tokens."""

    name = "FilterStep"

    def process(self, context: PipelineContext) -> PipelineContext:
        """Filter and normalize tokens.

        Args:
            context: The pipeline context.

        Returns:
            The updated context with filtered tokens.

        Raises:
            PipelineStepError: If filtering fails.
        """
        try:
            logger.info("Filtering tokens")
            context.data["filtered"] = True
            return context
        except Exception as exc:
            raise PipelineStepError(self.name, f"Filtering failed: {exc}") from exc


class FeatureExtractStep(PipelineStep):
    """Extracts features from filtered tokens for ML processing."""

    name = "FeatureExtractStep"

    def process(self, context: PipelineContext) -> PipelineContext:
        """Extract features from tokens.

        Args:
            context: The pipeline context.

        Returns:
            The updated context with extracted features.

        Raises:
            PipelineStepError: If feature extraction fails.
        """
        try:
            logger.info("Extracting features")
            context.data["features_extracted"] = True
            return context
        except Exception as exc:
            raise PipelineStepError(self.name, f"Feature extraction failed: {exc}") from exc


class TrainStep(PipelineStep):
    """Trains a model on the extracted features."""

    name = "TrainStep"

    def validate(self, context: PipelineContext) -> bool:
        """Validate that this is a training task.

        Args:
            context: The pipeline context.

        Returns:
            True if this is a training task, False otherwise.
        """
        return context.is_training

    def process(self, context: PipelineContext) -> PipelineContext:
        """Train a model on the features.

        Args:
            context: The pipeline context.

        Returns:
            The updated context with trained model info.

        Raises:
            PipelineStepError: If training fails.
        """
        try:
            logger.info(f"Training model: {context.model_name}")
            context.data["model_trained"] = True
            return context
        except Exception as e:
            raise PipelineStepError(self.name, f"Training failed: {e}")


class PredictStep(PipelineStep):
    """Runs predictions on the extracted features."""

    name = "PredictStep"

    def validate(self, context: PipelineContext) -> bool:
        """Validate that this is a prediction task.

        Args:
            context: The pipeline context.

        Returns:
            True if this is a prediction task, False otherwise.
        """
        return not context.is_training

    def process(self, context: PipelineContext) -> PipelineContext:
        """Run predictions on the features.

        Args:
            context: The pipeline context.

        Returns:
            The updated context with predictions.

        Raises:
            PipelineStepError: If prediction fails.
        """
        try:
            logger.info(f"Running predictions with model: {context.model_name}")
            context.data["predictions_made"] = True
            return context
        except Exception as e:
            raise PipelineStepError(self.name, f"Prediction failed: {e}")
