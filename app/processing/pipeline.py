"""Pipeline framework for Glyph processing layer.

This module provides a pluggable, extensible pipeline architecture for binary
analysis tasks. The framework is designed to be reusable across different
types of analysis workflows beyond ML training and prediction.

Python 3.11+
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import logging


@dataclass
class PipelineContext:
    """Context object carrying data through the pipeline.

    This context is designed to be extensible for various analysis types.
    It carries core metadata plus an arbitrary data payload that steps
    can read from and write to.

    Attributes:
        uuid: Unique identifier for this pipeline execution.
        binary_path: Path to the binary file being processed.
        pipeline_type: Type/category of pipeline (e.g., "ml_training", "ml_prediction", "static_analysis").
        metadata: Dictionary for pipeline-specific metadata.
        data: Arbitrary data payload for step-to-step communication.
        status: Current status of the pipeline execution.
        error: Error message if pipeline failed.
    """

    uuid: str
    binary_path: str
    pipeline_type: str = "generic"
    metadata: dict[str, Any] = field(default_factory=dict)
    data: dict[str, Any] = field(default_factory=dict)
    status: str = "starting"
    error: str | None = None

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the data payload.

        Args:
            key: The key to retrieve.
            default: Default value if key not found.

        Returns:
            The value associated with the key, or default.
        """
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a value in the data payload.

        Args:
            key: The key to set.
            value: The value to store.
        """
        self.data[key] = value

    def has(self, key: str) -> bool:
        """Check if a key exists in the data payload.

        Args:
            key: The key to check.

        Returns:
            True if the key exists.
        """
        return key in self.data


class PipelineStep(ABC):
    """Abstract base class for pipeline steps.

    Each step in the processing pipeline must implement this interface.
    Steps receive a PipelineContext, perform their operation, and return
    an updated context.

    Steps are designed to be:
    - Independent: Each step can be tested and used in isolation
    - Composable: Steps can be combined in different orders
    - Reusable: Steps can be shared across different pipelines
    """

    @abstractmethod
    def execute(self, context: PipelineContext) -> PipelineContext:
        """Execute this step and return updated context.

        Args:
            context: The pipeline context containing input data.

        Returns:
            Updated pipeline context with step results.

        Raises:
            Exception: If the step fails. The framework will catch this
                       and set context.error and context.status to "error".
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Return the name of this step.

        Returns:
            A string identifying this step.
        """
        pass

    def get_description(self) -> str:
        """Return a description of this step.

        Returns:
            A human-readable description of what this step does.
        """
        return f"{self.get_name()} step"


class ProcessingPipeline:
    """Orchestrates execution of pipeline steps.

    This class manages the execution of a sequence of PipelineStep instances,
    passing context between steps and handling errors. It is designed to be
    generic and reusable across different analysis workflows.
    """

    def __init__(self, name: str, steps: list[PipelineStep]) -> None:
        """Initialize a processing pipeline with the given steps.

        Args:
            name: A name identifying this pipeline configuration.
            steps: Ordered list of pipeline steps to execute.
        """
        self._name = name
        self._steps = steps
        self._logger = logging.getLogger(self.__class__.__name__)

    @property
    def name(self) -> str:
        """Return the name of this pipeline.

        Returns:
            The pipeline name.
        """
        return self._name

    @property
    def steps(self) -> list[PipelineStep]:
        """Return the list of steps in this pipeline.

        Returns:
            List of PipelineStep instances.
        """
        return self._steps

    def execute(self, context: PipelineContext) -> PipelineContext:
        """Execute all steps in the pipeline.

        Args:
            context: The initial pipeline context.

        Returns:
            The final pipeline context after all steps complete.
        """
        self._logger.info(
            "Starting pipeline '%s' execution for UUID: %s, steps: %d",
            self._name,
            context.uuid,
            len(self._steps),
        )

        for step in self._steps:
            try:
                self._logger.info("Executing step: %s", step.get_name())
                context = step.execute(context)

                # Check if step set an error
                if context.error is not None:
                    context.status = "error"
                    self._logger.error(
                        "Step %s failed: %s", step.get_name(), context.error
                    )
                    break

                self._logger.info(
                    "Step %s completed successfully", step.get_name()
                )

            except Exception as step_error:
                context.status = "error"
                context.error = str(step_error)
                self._logger.error(
                    "Step %s raised exception: %s",
                    step.get_name(),
                    step_error,
                    exc_info=True,
                )
                break

        if context.status != "error":
            context.status = "complete"
            self._logger.info("Pipeline '%s' execution completed successfully", self._name)

        return context

    def add_step(self, step: PipelineStep) -> "ProcessingPipeline":
        """Add a step to the end of this pipeline.

        Args:
            step: The step to add.

        Returns:
            Self for method chaining.
        """
        self._steps.append(step)
        return self

    def insert_step(self, index: int, step: PipelineStep) -> "ProcessingPipeline":
        """Insert a step at the specified position.

        Args:
            index: Position to insert the step.
            step: The step to insert.

        Returns:
            Self for method chaining.
        """
        self._steps.insert(index, step)
        return self

    def remove_step(self, step_name: str) -> bool:
        """Remove a step by name.

        Args:
            step_name: Name of the step to remove.

        Returns:
            True if a step was removed, False if not found.
        """
        for i, step in enumerate(self._steps):
            if step.get_name() == step_name:
                self._steps.pop(i)
                return True
        return False

    def get_step(self, step_name: str) -> PipelineStep | None:
        """Get a step by name.

        Args:
            step_name: Name of the step to retrieve.

        Returns:
            The step if found, None otherwise.
        """
        for step in self._steps:
            if step.get_name() == step_name:
                return step
        return None


class PipelineBuilder:
    """Builder for constructing pipelines with a fluent API.

    This builder allows for easy pipeline construction and customization.
    """

    def __init__(self, name: str) -> None:
        """Initialize the pipeline builder.

        Args:
            name: Name for the pipeline being built.
        """
        self._name = name
        self._steps: list[PipelineStep] = []

    def add_step(self, step: PipelineStep) -> "PipelineBuilder":
        """Add a step to the pipeline.

        Args:
            step: The step to add.

        Returns:
            Self for method chaining.
        """
        self._steps.append(step)
        return self

    def add_steps(self, *steps: PipelineStep) -> "PipelineBuilder":
        """Add multiple steps to the pipeline.

        Args:
            *steps: Variable number of steps to add.

        Returns:
            Self for method chaining.
        """
        self._steps.extend(steps)
        return self

    def build(self) -> ProcessingPipeline:
        """Build and return the pipeline.

        Returns:
            A ProcessingPipeline with the configured steps.
        """
        return ProcessingPipeline(self._name, self._steps)
