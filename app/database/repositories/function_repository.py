"""Repository for function database operations."""

import logging

from app.database.models import Function
from app.database.session_handler import get_session

logger = logging.getLogger(__name__)


class FunctionRepository:
    """Repository for managing function data in the database."""

    @staticmethod
    def save_functions(model_name: str, functions: list[dict]) -> list[Function]:
        """Save functions to the database.

        Args:
            model_name: Name of the model.
            functions: List of functions to save.

        Returns:
            List of created Function instances.
        """
        with get_session("functions") as session:
            saved_functions = []
            for function in functions:
                func = Function(
                    model_name=model_name,
                    function_name=function["functionName"],
                    entrypoint=function["lowAddress"],
                    tokens=function["tokens"],
                )
                session.add(func)
                saved_functions.append(func)
            return saved_functions

    @staticmethod
    def get_functions(model_name: str) -> list[Function]:
        """Get all functions for a model from the database.

        Args:
            model_name: Name of the model.

        Returns:
            List of Function instances.
        """
        with get_session("functions") as session:
            return session.query(Function).filter(Function.model_name == model_name).all()

    @staticmethod
    def get_function(model_name: str, function_name: str) -> Function | None:
        """Get a specific function from the database.

        Args:
            model_name: Name of the model.
            function_name: Name of the function.

        Returns:
            Function instance if found, otherwise None.
        """
        with get_session("functions") as session:
            return (
                session.query(Function)
                .filter(
                    Function.model_name == model_name,
                    Function.function_name == function_name,
                )
                .first()
            )

    @staticmethod
    def delete_functions(model_name: str) -> int:
        """Delete all functions for a model from the database.

        Args:
            model_name: Name of the model.

        Returns:
            Number of functions deleted.
        """
        with get_session("functions") as session:
            result = session.query(Function).filter(Function.model_name == model_name).delete()
            logger.info(f"Deleted {result} functions for model '{model_name}'.")
            return result
