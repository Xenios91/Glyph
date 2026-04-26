"""SQL utility module for database operations."""

import os
import sqlite3
from io import BytesIO
from typing import Any

import joblib

from app.services.request_handler import Prediction
from loguru import logger
from app.utils.secure_deserializer import secure_load, SecureDeserializationError


def _log_db_error(
    operation: str,
    error: Exception,
    context: dict[str, Any] | None = None) -> None:
    """Log a database error with structured context.

    Args:
        operation: The database operation that failed.
        error: The exception that occurred.
        context: Optional additional context data.
    """
    extra: dict[str, Any] = {"operation": operation}
    if context:
        extra.update(context)
    logger.bind(**extra).error(
        "Database error during {}: {}", operation, error)


class SQLUtil:
    """Utility class for SQLite database operations."""

    @staticmethod
    def init_db() -> None:
        """Initialize the database tables for models and predictions."""
        if not os.path.exists("models.db"):
            with sqlite3.connect("models.db") as con:
                try:
                    cur = con.cursor()
                    cur.execute(
                        "CREATE TABLE IF NOT EXISTS "
                        "models(model_name VARCHAR(64), model BLOB, label_encoder BLOB)"
                    )
                    con.commit()
                except sqlite3.Error as error:
                    _log_db_error("init_models_db", error)

        if not os.path.exists("predictions.db"):
            with sqlite3.connect("predictions.db") as con:
                try:
                    cur = con.cursor()
                    cur.execute(
                        "CREATE TABLE IF NOT EXISTS "
                        "PREDICTIONS(name VARCHAR(64), model_name VARCHAR(64), functions BLOB)"
                    )
                    con.commit()
                except sqlite3.Error as error:
                    _log_db_error("init_predictions_db", error)

    @staticmethod
    def save_model(model_name: str, label_encoder, model: bytes) -> None:
        """Save a model to the models database.

        Args:
            model_name: Name of the model to save.
            label_encoder: The label encoder to save.
            model: The model bytes to save.
        """
        with sqlite3.connect("models.db") as con:
            try:
                cur = con.cursor()
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS "
                    "models(model_name VARCHAR(64), model BLOB, label_encoder BLOB)"
                )
                sql = "INSERT INTO models (model_name, model, label_encoder) VALUES (?, ?, ?)"
                cur.execute(
                    sql,
                    (model_name, sqlite3.Binary(model), sqlite3.Binary(label_encoder)))
                con.commit()
                logger.info("Model '{}' saved successfully", model_name)
            except sqlite3.Error as error:
                _log_db_error("save_model", error, {"model_name": model_name})

    @staticmethod
    def get_models_list() -> set[str]:
        """Get the list of model names from the database.

        Returns:
            A set of model names.
        """
        models_set: set[str] = set()
        if os.path.exists("models.db"):
            with sqlite3.connect("models.db") as con:
                try:
                    cur = con.cursor()
                    sql = "SELECT * FROM MODELS"
                    models = cur.execute(sql).fetchall()
                    for model in models:
                        models_set.add(model[0])
                except sqlite3.Error as error:
                    _log_db_error("get_models_list", error)
        return models_set

    @staticmethod
    def get_model(model_name: str) -> tuple[Any, ...] | None:
        """Retrieve the model row from the SQLite database.

        Args:
            model_name: Name of the model to retrieve.

        Returns:
            The tuple if found, otherwise None.
        """
        db_path = "models.db"
        try:
            with sqlite3.connect(db_path) as con:
                con.row_factory = sqlite3.Row
                cur = con.cursor()
                sql = "SELECT * FROM MODELS WHERE model_name = ?"
                model = cur.execute(sql, (model_name,)).fetchone()
                if model:
                    return model
                logger.warning("Model '{}' not found.", model_name)
                return None
        except sqlite3.Error as error:
            _log_db_error("get_model", error, {"model_name": model_name})
            return None

    @staticmethod
    def delete_model(model_name: str) -> None:
        """Delete a model and its associated functions from the database.

        Args:
            model_name: Name of the model to delete.
        """
        with sqlite3.connect("models.db") as con:
            try:
                SQLUtil.delete_functions(model_name)
                cur = con.cursor()
                sql = "DELETE FROM MODELS WHERE model_name=?"
                cur.execute(sql, (model_name,))
                con.commit()
                logger.info("Model '{}' deleted successfully", model_name)
            except sqlite3.Error as error:
                _log_db_error("delete_model", error, {"model_name": model_name})

    @staticmethod
    def get_predictions_list() -> list[Prediction]:
        """Get the list of all predictions from the database.

        Returns:
            A list of Prediction objects.
        """
        prediction_results: list[Prediction] = []
        if os.path.exists("predictions.db"):
            with sqlite3.connect("predictions.db") as con:
                try:
                    cur = con.cursor()
                    sql = "SELECT * FROM PREDICTIONS"
                    predictions = cur.execute(sql).fetchall()
                    for prediction in predictions:
                        try:
                            preds = secure_load(BytesIO(prediction[2]))
                            if not isinstance(preds, list):
                                logger.warning(
                                    "Prediction data for '{}' is not a list, skipping",
                                    prediction[0])
                                continue
                            prediction_results.append(
                                Prediction(prediction[0], prediction[1], preds)
                            )
                        except SecureDeserializationError as deserial_error:
                            logger.error(
                                "Secure deserialization blocked prediction '{}': {}",
                                prediction[0],
                                deserial_error)
                        except Exception as deserial_error:
                            logger.error(
                                "Failed to deserialize prediction '{}': {}",
                                prediction[0],
                                deserial_error)
                except sqlite3.Error as error:
                    _log_db_error("get_predictions_list", error)
        return prediction_results

    @staticmethod
    def get_predictions(task_name: str, model_name: str) -> "Prediction | None":
        """Retrieve and deserialize a Prediction object from the database.

        Args:
            task_name: Name of the task.
            model_name: Name of the model.

        Returns:
            Prediction object if found, otherwise None.
        """
        db_path = "predictions.db"
        if not os.path.exists(db_path):
            logger.warning("Database {} does not exist.", db_path)
            return None

        try:
            with sqlite3.connect(db_path) as con:
                cur = con.cursor()
                sql = "SELECT * FROM PREDICTIONS WHERE name=? AND model_name=?"
                row = cur.execute(sql, (task_name, model_name)).fetchone()
                if row is None:
                    return None

                try:
                    prediction_data = secure_load(BytesIO(row[2]))
                    if not isinstance(prediction_data, list):
                        logger.warning(
                            "Prediction data for task '{}' is not a list, expected list"
                            " got {}",
                            task_name,
                            type(prediction_data).__name__)
                        return None
                except SecureDeserializationError as deserial_error:
                    logger.error(
                        "Secure deserialization blocked prediction for task '{}': {}",
                        task_name,
                        deserial_error)
                    return None
                except Exception as deserial_error:
                    logger.error(
                        "Failed to deserialize prediction for task '{}': {}",
                        task_name,
                        deserial_error)
                    return None

                return Prediction(
                    task_name=task_name, model_name=model_name, pred=prediction_data
                )
        except sqlite3.Error as error:
            _log_db_error("get_predictions", error, {"task_name": task_name, "model_name": model_name})
            return None
        except Exception as error:
            logger.error("Unexpected error: {}", error)
            return None

    @staticmethod
    def save_predictions(name: str, model_name: str, functions: list) -> None:
        """Save predictions to the database.

        Args:
            name: Name of the task.
            model_name: Name of the model used.
            functions: List of function predictions to save.
        """
        with sqlite3.connect("predictions.db") as con:
            try:
                cur = con.cursor()
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS "
                    "PREDICTIONS(name VARCHAR(64), model_name VARCHAR(64), functions BLOB)"
                )
                sql = "INSERT INTO PREDICTIONS (name, model_name, functions) VALUES (?, ?, ?)"

                functions_buffer = BytesIO()
                joblib.dump(functions, functions_buffer)
                functions_serialized = functions_buffer.getvalue()
                cur.execute(
                    sql, (name, model_name, sqlite3.Binary(functions_serialized))
                )
                con.commit()
                logger.info("Prediction for task '{}' with model '{}' saved successfully", name, model_name)
            except sqlite3.Error as error:
                _log_db_error("save_predictions", error, {"task_name": name, "model_name": model_name})

    @staticmethod
    def get_prediction_function(
        task_name: str, model_name: str, function_name: str
    ) -> dict:
        """Get a specific function prediction from the database.

        Args:
            task_name: Name of the task.
            model_name: Name of the model.
            function_name: Name of the function to retrieve.

        Returns:
            Dictionary containing function prediction data, or empty dict if not found.
        """
        with sqlite3.connect("predictions.db") as con:
            try:
                cur = con.cursor()
                sql = "SELECT * FROM PREDICTIONS WHERE model_name=? and name=?"
                result = cur.execute(sql, (model_name, task_name)).fetchone()
                if result is None:
                    return {}
                try:
                    predictions = secure_load(BytesIO(result[2]))
                    if not isinstance(predictions, list):
                        logger.warning(
                            "Predictions data is not a list, expected list got {}",
                            type(predictions).__name__)
                        return {}
                    for function in predictions:
                        if (
                            isinstance(function, dict)
                            and function.get("functionName") == function_name
                        ):
                            return function
                except SecureDeserializationError as deserial_error:
                    logger.error(
                        "Secure deserialization blocked predictions: {}", deserial_error)
                    return {}
                except Exception as deserial_error:
                    logger.error(
                        "Failed to deserialize predictions: {}", deserial_error)
                    return {}
            except sqlite3.Error as error:
                _log_db_error("get_prediction_function", error, {"task_name": task_name, "model_name": model_name, "function_name": function_name})
        return {}

    @staticmethod
    def save_functions(model_name: str, functions: list) -> None:
        """Save functions to the functions database.

        Args:
            model_name: Name of the model.
            functions: List of functions to save.
        """
        with sqlite3.connect("functions.db") as con:
            try:
                cur = con.cursor()
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS "
                    "functions(model_name VARCHAR(64), function_name VARCHAR(64), "
                    "entrypoint VARCHAR(16), tokens TEXT)"
                )
                for function in functions:
                    sql = "INSERT INTO functions (model_name, function_name, entrypoint, tokens) VALUES (?, ?, ?, ?)"
                    tokens = " ".join(function["tokenList"])
                    cur.execute(
                        sql,
                        (
                            model_name,
                            function["functionName"],
                            function["lowAddress"],
                            tokens))
                con.commit()
                logger.info("Saved {} functions to model '{}'", len(functions), model_name)
            except sqlite3.Error as error:
                _log_db_error("save_functions", error, {"model_name": model_name})

    @staticmethod
    def get_functions(model_name: str) -> list:
        """Get all functions for a model from the database.

        Args:
            model_name: Name of the model.

        Returns:
            List of function records.
        """
        functions: list = []
        with sqlite3.connect("functions.db") as con:
            try:
                cur = con.cursor()
                sql = "SELECT * FROM FUNCTIONS WHERE model_name=?"
                functions = cur.execute(sql, (model_name,)).fetchall()
            except sqlite3.Error as error:
                _log_db_error("get_functions", error, {"model_name": model_name})
        return functions

    @staticmethod
    def get_function(model_name: str, function_name: str) -> list:
        """Get a specific function from the database.

        Args:
            model_name: Name of the model.
            function_name: Name of the function.

        Returns:
            Function record or empty list.
        """
        function_information: list = []
        with sqlite3.connect("functions.db") as con:
            try:
                cur = con.cursor()
                sql = "SELECT * FROM FUNCTIONS WHERE model_name=? and function_name=?"
                function_information = cur.execute(
                    sql, (model_name, function_name)
                ).fetchone()
            except sqlite3.Error as error:
                _log_db_error("get_function", error, {"model_name": model_name, "function_name": function_name})
            return function_information

    @staticmethod
    def delete_functions(model_name: str) -> None:
        """Delete all functions for a model from the database.

        Args:
            model_name: Name of the model.
        """
        with sqlite3.connect("functions.db") as con:
            try:
                cur = con.cursor()
                sql = "DELETE FROM FUNCTIONS WHERE model_name=?"
                cur.execute(sql, (model_name,))
                con.commit()
                logger.info("Functions for model '{}' deleted successfully", model_name)
            except sqlite3.Error as error:
                _log_db_error("delete_functions", error, {"model_name": model_name})

    @staticmethod
    def delete_prediction(task_name: str) -> None:
        """Delete a prediction from the database.

        Args:
            task_name: Name of the task to delete.
        """
        with sqlite3.connect("predictions.db") as con:
            try:
                cur = con.cursor()
                sql = "DELETE FROM PREDICTIONS WHERE name=?"
                cur.execute(sql, (task_name,))
                con.commit()
                logger.info("Prediction for task '{}' deleted successfully", task_name)
            except sqlite3.Error as error:
                _log_db_error("delete_prediction", error, {"task_name": task_name})
                raise

    @staticmethod
    def delete_model_predictions(model_name: str) -> None:
        """Delete all predictions for a model from the database.

        Args:
            model_name: Name of the model.
        """
        with sqlite3.connect("predictions.db") as con:
            try:
                cur = con.cursor()
                sql = "DELETE FROM PREDICTIONS WHERE model_name=?"
                cur.execute(sql, (model_name,))
                con.commit()
                logger.info("Predictions for model '{}' deleted successfully", model_name)
            except sqlite3.Error as error:
                _log_db_error("delete_model_predictions", error, {"model_name": model_name})

    @staticmethod
    def task_name_exists(task_name: str) -> bool:
        """Check if a task name already exists in the predictions database.

        Args:
            task_name: Name of the task to check.

        Returns:
            True if the task name exists, False otherwise.
        """
        db_path = "predictions.db"
        if not os.path.exists(db_path):
            return False

        try:
            with sqlite3.connect(db_path) as con:
                cur = con.cursor()
                sql = "SELECT COUNT(*) FROM PREDICTIONS WHERE name=?"
                result = cur.execute(sql, (task_name,)).fetchone()
                count = result[0] if result else 0
                return count > 0
        except sqlite3.Error as error:
            _log_db_error("task_name_exists", error, {"task_name": task_name})
            return False
