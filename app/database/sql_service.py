"""SQL utility module for database operations."""

import logging
import os
import sqlite3
from io import BytesIO
from typing import Any

import joblib

from app.services.request_handler import Prediction


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
                    logging.error("Database error: %s", error)

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
                    logging.error("Database error: %s", error)

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
                    (model_name, sqlite3.Binary(model), sqlite3.Binary(label_encoder)),
                )
                con.commit()
            except sqlite3.Error as error:
                logging.error("Database error: %s", error)

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
                    logging.error("Database error: %s", error)
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
                logging.warning("Model '%s' not found.", model_name)
                return None
        except sqlite3.Error as error:
            logging.error("Database error: %s", error)
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
            except sqlite3.Error as error:
                logging.error("Database error: %s", error)

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
                            preds = joblib.load(BytesIO(prediction[2]))
                            if not isinstance(preds, list):
                                logging.warning(
                                    "Prediction data for '%s' is not a list, skipping",
                                    prediction[0],
                                )
                                continue
                            prediction_results.append(
                                Prediction(prediction[0], prediction[1], preds)
                            )
                        except Exception as deserial_error:
                            logging.error(
                                "Failed to deserialize prediction '%s': %s",
                                prediction[0],
                                deserial_error,
                            )
                except sqlite3.Error as error:
                    logging.error("Database error: %s", error)
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
            logging.warning("Database %s does not exist.", db_path)
            return None

        try:
            with sqlite3.connect(db_path) as con:
                cur = con.cursor()
                sql = "SELECT * FROM PREDICTIONS WHERE name=? AND model_name=?"
                row = cur.execute(sql, (task_name, model_name)).fetchone()
                if row is None:
                    return None

                try:
                    prediction_data = joblib.load(BytesIO(row[2]))
                    if not isinstance(prediction_data, list):
                        logging.warning(
                            "Prediction data for task '%s' is not a list, expected list"
                            " got %s",
                            task_name,
                            type(prediction_data).__name__,
                        )
                        return None
                except Exception as deserial_error:
                    logging.error(
                        "Failed to deserialize prediction for task '%s': %s",
                        task_name,
                        deserial_error,
                    )
                    return None

                return Prediction(
                    task_name=task_name, model_name=model_name, pred=prediction_data
                )
        except sqlite3.Error as error:
            logging.error("Database error: %s", error)
            return None
        except Exception as error:
            logging.error("Unexpected error: %s", error)
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
            except sqlite3.Error as error:
                logging.error("Database error: %s", error)

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
                    predictions = joblib.load(BytesIO(result[2]))
                    if not isinstance(predictions, list):
                        logging.warning(
                            "Predictions data is not a list, expected list got %s",
                            type(predictions).__name__,
                        )
                        return {}
                    for function in predictions:
                        if isinstance(function, dict) and function.get(
                            "functionName"
                        ) == function_name:
                            return function
                except Exception as deserial_error:
                    logging.error("Failed to deserialize predictions: %s", deserial_error)
                    return {}
            except sqlite3.Error as error:
                logging.error("Database error: %s", error)
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
                    tokens = function["tokens"]
                    cur.execute(
                        sql,
                        (
                            model_name,
                            function["functionName"],
                            function["lowAddress"],
                            tokens,
                        ),
                    )
                con.commit()
            except sqlite3.Error as error:
                logging.error("Database error: %s", error)

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
                logging.error("Database error: %s", error)
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
                logging.error("Database error: %s", error)
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
            except sqlite3.Error as error:
                logging.error("Database error: %s", error)

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
            except sqlite3.Error as error:
                logging.error("Database error: %s", error)

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
            except sqlite3.Error as error:
                logging.error("Database error: %s", error)