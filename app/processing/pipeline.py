"""Processing pipeline abstraction for Glyph application.

Provides a pluggable pipeline pattern for binary processing with steps for
validation, decompilation, tokenization, filtering, and feature extraction.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class PipelineStepStatus(Enum):
    """Status of a pipeline step execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PipelineContext:
    """Context object passed through pipeline steps.

    Attributes:
        binary_path: Path to the binary file being processed.
        model_name: Name of the model to use.
        task_name: Name of the task.
        is_training: Whether this is a training or prediction task.
        data: Dictionary for passing data between steps.
        status: Current status of the pipeline.
        error: Error message if pipeline failed.
        started_at: Timestamp when pipeline started.
        completed_at: Timestamp when pipeline completed.
    """

    binary_path: str
    model_name: str
    task_name: str
    is_training: bool
    data: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class PipelineStep(ABC):
    """Abstract base class for pipeline steps.

    Each step implements a single processing operation and can be
    composed into a pipeline.
    """

    name: str = "BaseStep"

    @abstractmethod
    def process(self, context: PipelineContext) -> PipelineContext:
        """Process the context and return the updated context.

        Args:
            context: The pipeline context containing data.

        Returns:
            The updated pipeline context.

        Raises:
            PipelineStepError: If the step fails.
        """
        pass

    def validate(self, context: PipelineContext) -> bool:
        """Validate that the context has required data for this step.

        Args:
            context: The pipeline context to validate.

        Returns:
            True if validation passes, False otherwise.
        """
        return True


class PipelineStepError(Exception):
    """Exception raised when a pipeline step fails."""

    def __init__(self, step_name: str, message: str) -> None:
        self.step_name = step_name
        self.message = message
        super().__init__(f"{step_name}: {message}")


class ProcessingPipeline:
    """Pipeline for processing binaries through multiple steps.

    The pipeline executes steps in order, passing context between them.
    If any step fails, the pipeline stops and marks the context as failed.

    Attributes:
        steps: List of pipeline steps to execute.
    """

    def __init__(self, steps: list[PipelineStep] | None = None) -> None:
        """Initialize the processing pipeline.

        Args:
            steps: Optional list of steps. If not provided, an empty list is used.
        """
        self.steps = steps if steps is not None else []

    def add_step(self, step: PipelineStep) -> "ProcessingPipeline":
        """Add a step to the pipeline.

        Args:
            step: The step to add.

        Returns:
            Self for method chaining.
        """
        self.steps.append(step)
        return self

    def process(self, context: PipelineContext) -> PipelineContext:
        """Process the context through all pipeline steps.

        Args:
            context: The pipeline context to process.

        Returns:
            The processed pipeline context.
        """
        context.started_at = datetime.utcnow()
        context.status = "running"

        for step in self.steps:
            try:
                if not step.validate(context):
                    context.status = "skipped"
                    continue

                context = step.process(context)
            except PipelineStepError as e:
                context.status = "failed"
                context.error = str(e)
                context.completed_at = datetime.utcnow()
                return context

        context.status = "completed"
        context.completed_at = datetime.utcnow()
        return context
