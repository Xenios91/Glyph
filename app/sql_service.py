import logging
import os
import pickle
import sqlite3
from typing import Any

from app.request_handler import Prediction


class SQLUtil:
    @staticmethod
    def init_db():
        if not os.path.exists("models.db"):
            with sqlite3.connect("models.db") as con:
                try:
                    cur = con.cursor()
                    cur.execute(
                        "CREATE TABLE IF NOT EXISTS models(model_name VARCHAR(64), model BLOB, label_encoder BLOB)"
                    )

                    con.commit()
                except Exception as error:
                    logging.error(error)

        if not os.path.exists("predictions.db"):
            with sqlite3.connect("predictions.db") as con:
                try:
                    cur = con.cursor()
                    cur.execute(
                        "CREATE TABLE IF NOT EXISTS PREDICTIONS(name VARCHAR(64), model_name VARCHAR(64), functions BLOB)"
                    )
                    con.commit()
                except Exception as error:
                    logging.error(error)

    @staticmethod
    def save_model(model_name: str, label_encoder, model: bytes):
        with sqlite3.connect("models.db") as con:
            try:
                cur = con.cursor()
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS models(model_name VARCHAR(64), model BLOB, label_encoder BLOB)"
                )

                sql = "INSERT INTO models (model_name, model, label_encoder) VALUES (?, ?, ?)"
                cur.execute(
                    sql,
                    (model_name, sqlite3.Binary(model), sqlite3.Binary(label_encoder)),
                )
                con.commit()
            except Exception as error:
                logging.error(error)

    @staticmethod
    def get_models_list() -> set[str]:
        models_set: set[str] = set()
        if os.path.exists("models.db"):
            with sqlite3.connect("models.db") as con:
                try:
                    cur = con.cursor()
                    sql = "SELECT * FROM MODELS"
                    models = cur.execute(sql).fetchall()
                    for model in models:
                        models_set.add(model[0])

                except Exception as error:
                    logging.error(error)

        return models_set

    @staticmethod
    def get_model(model_name: str) -> tuple[Any, ...] | None:
        """
        Retrieves the model row from the SQLite database.
        Returns the tuple (row) if found, otherwise None.
        """
        db_path = "models.db"

        try:
            with sqlite3.connect(db_path) as con:
                # Optional: This allows accessing columns by name like row['model_name']
                con.row_factory = sqlite3.Row
                cur = con.cursor()

                sql = "SELECT * FROM MODELS WHERE model_name = ?"
                model = cur.execute(sql, (model_name,)).fetchone()

                if model:
                    return model

                logging.warning(f"Model '{model_name}' not found.")
                return None

        except sqlite3.Error as error:
            logging.error(f"Database error: {error}")
            return None

    @staticmethod
    def delete_model(model_name: str):
        with sqlite3.connect("models.db") as con:
            try:
                SQLUtil.delete_functions(model_name)

                cur = con.cursor()
                sql = "DELETE FROM MODELS WHERE model_name=?"
                cur.execute(sql, (model_name,))
                con.commit()
            except Exception as error:
                logging.error(error)

    @staticmethod
    def get_predictions_list() -> list[Prediction]:
        prediction_results: list[Prediction] = []
        if os.path.exists("predictions.db"):
            with sqlite3.connect("predictions.db") as con:
                try:
                    cur = con.cursor()
                    sql = "SELECT * FROM PREDICTIONS"
                    predictions = cur.execute(sql).fetchall()
                    for prediction in predictions:
                        preds = pickle.loads(prediction[2])
                        prediction_results.append(
                            Prediction(prediction[0], prediction[1], preds)
                        )
                except Exception as error:
                    logging.error(error)

        return prediction_results

    @staticmethod
    def get_predictions(task_name: str, model_name: str) -> "Prediction | None":
        """
        Retrieves and unserializes a Prediction object from the database.
        """
        db_path = "predictions.db"

        if not os.path.exists(db_path):
            logging.warning(f"Database {db_path} does not exist.")
            return None

        try:
            with sqlite3.connect(db_path) as con:
                cur = con.cursor()
                sql = "SELECT * FROM PREDICTIONS WHERE name=? AND model_name=?"
                row = cur.execute(sql, (task_name, model_name)).fetchone()

                if row is None:
                    return None

                prediction_data = pickle.loads(row[2])

                return Prediction(
                    task_name=task_name, model_name=model_name, pred=prediction_data
                )

        except (sqlite3.Error, pickle.UnpicklingError, IndexError) as error:
            logging.error(f"Error retrieving/unpickling prediction: {error}")
            return None
        except Exception as error:
            logging.error(f"Unexpected error: {error}")
            return None

    @staticmethod
    def save_predictions(name: str, model_name: str, functions: list) -> None:
        with sqlite3.connect("predictions.db") as con:
            try:
                cur = con.cursor()
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS PREDICTIONS(name VARCHAR(64), model_name VARCHAR(64), functions BLOB)"
                )
                sql = "INSERT INTO PREDICTIONS (name, model_name, functions) VALUES (?, ?, ?)"

                functions_serialized = pickle.dumps(functions)
                cur.execute(
                    sql, (name, model_name, sqlite3.Binary(functions_serialized))
                )

                con.commit()
            except Exception as error:
                logging.error(error)

    @staticmethod
    def get_prediction_function(
        task_name: str, model_name: str, function_name: str
    ) -> dict:
        with sqlite3.connect("predictions.db") as con:
            try:
                cur = con.cursor()
                sql = "SELECT * FROM PREDICTIONS WHERE model_name=? and name=?"
                result = cur.execute(
                    sql,
                    (
                        model_name,
                        task_name,
                    ),
                ).fetchone()
                predictions = pickle.loads(result[2])
                for function in predictions:
                    if function["functionName"] == function_name:
                        return function
            except Exception as error:
                logging.error(error)

        return {}

    @staticmethod
    def save_functions(model_name: str, functions: list):
        with sqlite3.connect("functions.db") as con:
            try:
                cur = con.cursor()
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS functions(model_name VARCHAR(64), function_name VARCHAR(64), entrypoint VARCHAR(16), tokens TEXT)"
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
            except Exception as error:
                logging.error(error)

    @staticmethod
    def get_functions(model_name: str) -> list:
        functions: list = []
        with sqlite3.connect("functions.db") as con:
            try:
                cur = con.cursor()
                sql = "SELECT * FROM FUNCTIONS WHERE model_name=?"
                functions = cur.execute(sql, (model_name,)).fetchall()
            except Exception as error:
                logging.error(error)

        return functions

    @staticmethod
    def get_function(model_name: str, function_name: str) -> list:
        function_information: list = []
        with sqlite3.connect("functions.db") as con:
            try:
                cur = con.cursor()
                sql = "SELECT * FROM FUNCTIONS WHERE model_name=? and function_name=?"
                function_information = cur.execute(
                    sql,
                    (
                        model_name,
                        function_name,
                    ),
                ).fetchone()
            except Exception as error:
                logging.error(error)

            return function_information

    @staticmethod
    def delete_functions(model_name: str):
        with sqlite3.connect("functions.db") as con:
            try:
                cur = con.cursor()
                sql = "DELETE FROM FUNCTIONS WHERE model_name=?"
                cur.execute(sql, (model_name,))
                con.commit()
            except Exception as error:
                logging.error(error)

    @staticmethod
    def delete_prediction(task_name: str):
        with sqlite3.connect("predictions.db") as con:
            try:
                cur = con.cursor()
                sql = "DELETE FROM PREDICTIONS WHERE name=?"
                cur.execute(sql, (task_name,))
                con.commit()
            except Exception as error:
                logging.error(error)

    @staticmethod
    def delete_model_predictions(model_name: str):
        with sqlite3.connect("predictions.db") as con:
            try:
                cur = con.cursor()
                sql = "DELETE FROM PREDICTIONS WHERE model_name=?"
                cur.execute(sql, (model_name,))
                con.commit()
            except Exception as error:
                logging.error(error)
