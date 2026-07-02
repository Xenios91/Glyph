"""Custom exceptions for Glyph service layer."""


class BinaryNotFoundError(Exception):
    """Raised when a binary is not found."""

    def __init__(self, binary_id: int) -> None:
        self.binary_id = binary_id
        super().__init__(f"Binary with id {binary_id} not found")


class BinaryAccessError(Exception):
    """Raised when user tries to access another user's binary."""

    def __init__(self, binary_id: int, user_id: int) -> None:
        self.binary_id = binary_id
        self.user_id = user_id
        super().__init__(f"User {user_id} does not have access to binary {binary_id}")


class ValidationError(Exception):
    """Raised when input validation fails."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class ModelNotFoundError(Exception):
    """Raised when a model is not found."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        super().__init__(f"Model '{model_name}' not found")


class TaskNameExistsError(Exception):
    """Raised when task name is not unique."""

    def __init__(self, task_name: str) -> None:
        self.task_name = task_name
        super().__init__(f"Task name '{task_name}' already exists")


class PredictionNotFoundError(Exception):
    """Raised when a prediction is not found."""

    def __init__(self, task_name: str, model_name: str) -> None:
        self.task_name = task_name
        self.model_name = model_name
        super().__init__(f"Prediction for task '{task_name}' and model '{model_name}' not found")


class SimilarityComputationNotFoundError(Exception):
    """Raised when a similarity computation is not found."""

    def __init__(self, computation_id: int) -> None:
        self.computation_id = computation_id
        super().__init__(f"Similarity computation with id {computation_id} not found")


class SimilarityComputationAccessError(Exception):
    """Raised when user tries to access another user's similarity computation."""

    def __init__(self, computation_id: int, user_id: int) -> None:
        self.computation_id = computation_id
        self.user_id = user_id
        super().__init__(f"User {user_id} does not have access to similarity computation {computation_id}")
