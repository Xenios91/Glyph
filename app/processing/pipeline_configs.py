"""Predefined pipeline configurations for Glyph processing workflows.

Centralizes pipeline step compositions so that each workflow is defined
in a single location. Adding, removing, or reordering a step affects
all callers automatically.

Available Pipelines
-------------------
UPLOAD_PIPELINE
    Validates the binary file, decompiles it with Ghidra, and saves
    raw function output to the BinaryFunction table. Used when a new
    binary is uploaded.

TRAINING_PIPELINE
    Full ML training workflow: validate, decompile, tokenize, filter,
    extract features, and train the classification model.

PREDICTION_PIPELINE
    Full ML prediction workflow: validate, decompile, tokenize, filter,
    extract features, and run predictions against a trained model.

ML_PREDICTION_ONLY_PIPELINE
    Lightweight prediction workflow that skips validation and
    decompilation. Expects functions to already be loaded in the
    context (e.g., from PredictionRequest data).

TRAINING_FROM_DB_PIPELINE
    ML training workflow that loads previously stored functions from
    the BinaryFunction table instead of re-decompiling. Used by the
    task execution endpoints.

PREDICTION_FROM_DB_PIPELINE
    ML prediction workflow that loads previously stored functions from
    the BinaryFunction table instead of re-decompiling. Used by the
    task execution endpoints.
"""

from app.processing.pipeline import ProcessingPipeline
from app.processing.steps import (
    DecompileStep,
    FeatureExtractStep,
    FilterStep,
    LoadBinaryFunctionsStep,
    PredictStep,
    SaveRawFunctionsStep,
    TokenizeStep,
    TrainStep,
    ValidationStep,
)

# Binary upload — validate, decompile, save raw functions
UPLOAD_PIPELINE = ProcessingPipeline(
    "Binary Upload Pipeline",
    [
        ValidationStep(),
        DecompileStep(),
        SaveRawFunctionsStep(),
    ],
)

# ML training — full pipeline from binary to trained model
TRAINING_PIPELINE = ProcessingPipeline(
    "ML Training Pipeline",
    [
        ValidationStep(),
        DecompileStep(),
        TokenizeStep(),
        FilterStep(),
        FeatureExtractStep(),
        TrainStep(),
    ],
)

# ML prediction — full pipeline from binary to predictions
PREDICTION_PIPELINE = ProcessingPipeline(
    "ML Prediction Pipeline",
    [
        ValidationStep(),
        DecompileStep(),
        TokenizeStep(),
        FilterStep(),
        FeatureExtractStep(),
        PredictStep(),
    ],
)

# ML prediction without decompilation — functions already in context
ML_PREDICTION_ONLY_PIPELINE = ProcessingPipeline(
    "ML Prediction (No Decompilation)",
    [
        TokenizeStep(),
        FilterStep(),
        FeatureExtractStep(),
        PredictStep(),
    ],
)

# ML training from previously stored functions in database
TRAINING_FROM_DB_PIPELINE = ProcessingPipeline(
    "ML Training (From Database)",
    [
        LoadBinaryFunctionsStep(),
        TokenizeStep(),
        FilterStep(),
        FeatureExtractStep(),
        TrainStep(),
    ],
)

# ML prediction from previously stored functions in database
PREDICTION_FROM_DB_PIPELINE = ProcessingPipeline(
    "ML Prediction (From Database)",
    [
        LoadBinaryFunctionsStep(),
        TokenizeStep(),
        FilterStep(),
        FeatureExtractStep(),
        PredictStep(),
    ],
)

__all__ = [
    "ML_PREDICTION_ONLY_PIPELINE",
    "PREDICTION_FROM_DB_PIPELINE",
    "PREDICTION_PIPELINE",
    "TRAINING_FROM_DB_PIPELINE",
    "TRAINING_PIPELINE",
    "UPLOAD_PIPELINE",
]
