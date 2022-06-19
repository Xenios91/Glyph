import os
import pickle
import sqlite3

from request_handler import Prediction


class SQLUtil():

    @staticmethod
    def save_model(model_name: str, label_encoder, model: bytes):
        with sqlite3.connect('models.db') as con:
            try:
                cur = con.cursor()
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS models(model_name VARCHAR(64), model BLOB, label_encoder BLOB)")

                sql = "INSERT INTO models (model_name, model, label_encoder) VALUES (?, ?, ?)"
                cur.execute(sql, (model_name, sqlite3.Binary(
                    model), sqlite3.Binary(label_encoder)))
                con.commit()
            except Exception as e:
                print(e)

    @staticmethod
    def get_models_list() -> set[str]:
        models_set: set[str] = set()
        if os.path.exists("models.db"):
            with sqlite3.connect('models.db') as con:
                try:
                    cur = con.cursor()
                    sql = "SELECT * FROM MODELS"
                    models = cur.execute(sql).fetchall()
                    for model in models:
                        models_set.add(model[0])

                except Exception as e:
                    print(e)

        return models_set

    @staticmethod
    def get_model(model_name: str) -> bytes:
        model: bytes
        with sqlite3.connect('models.db') as con:
            try:
                cur = con.cursor()
                sql = "SELECT * FROM MODELS WHERE model_name=?"
                model = cur.execute(sql, (model_name,)).fetchone()
            except Exception as e:
                print(e)
        return model

    @staticmethod
    def delete_model(model_name: str):
        with sqlite3.connect('models.db') as con:
            try:
                SQLUtil.delete_functions(model_name)

                cur = con.cursor()
                sql = "DELETE FROM MODELS WHERE model_name=?"
                cur.execute(sql, (model_name,))
                con.commit()
            except Exception as e:
                print(e)

    @staticmethod
    def get_predictions_list() -> list[Prediction]:
        prediction_results: list[Prediction] = []
        if os.path.exists("predictions.db"):
            with sqlite3.connect('predictions.db') as con:
                try:
                    cur = con.cursor()
                    sql = "SELECT * FROM PREDICTIONS"
                    predictions = cur.execute(sql).fetchall()
                    for prediction in predictions:
                        preds = pickle.loads(prediction[2])
                        prediction_results.append(Prediction(
                            prediction[0], prediction[1], preds))
                except Exception as e:
                    print(e)

        return prediction_results

    @staticmethod
    def get_predictions(task_name: str, model_name: str) -> Prediction:
        if os.path.exists("predictions.db"):
            with sqlite3.connect('predictions.db') as con:
                try:
                    cur = con.cursor()
                    sql = "SELECT * FROM PREDICTIONS WHERE name=? and model_name=?"
                    prediction = cur.execute(
                        sql, (task_name, model_name,)).fetchone()
                    prediction_unserialized = pickle.loads(prediction[2])
                    pred: Prediction = Prediction(
                        model_name, task_name, prediction_unserialized)
                except Exception as e:
                    print(e)

        return pred

    @staticmethod
    def save_predictions(name: str, model_name: str, functions: list) -> None:
        with sqlite3.connect('predictions.db') as con:
            try:
                cur = con.cursor()
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS PREDICTIONS(name VARCHAR(64), model_name VARCHAR(64), functions BLOB)")
                sql = "INSERT INTO PREDICTIONS (name, model_name, functions) VALUES (?, ?, ?)"

                functions_serialized = pickle.dumps(functions)
                cur.execute(
                    sql, (name, model_name, sqlite3.Binary(functions_serialized)))

                con.commit()
            except Exception as e:
                print(e)

    @staticmethod
    def get_prediction_function(task_name: str, model_name: str, function_name: str) -> dict:
        with sqlite3.connect('predictions.db') as con:
            try:
                cur = con.cursor()
                sql = "SELECT * FROM PREDICTIONS WHERE model_name=? and name=?"
                result = cur.execute(
                    sql, (model_name, task_name,)).fetchone()
                predictions = pickle.loads(result[2])
                for function in predictions:
                    if function["functionName"] == function_name:
                        return function
            except Exception as e:
                print(e)

        return {}

    @staticmethod
    def save_functions(model_name: str, functions: list):
        with sqlite3.connect('functions.db') as con:
            try:
                cur = con.cursor()
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS functions(model_name VARCHAR(64), function_name VARCHAR(64), entrypoint VARCHAR(16), tokens TEXT)")
                for function in functions:
                    sql = "INSERT INTO functions (model_name, function_name, entrypoint, tokens) VALUES (?, ?, ?, ?)"
                    tokens = function["tokens"]
                    cur.execute(
                        sql, (model_name, function["functionName"], function["lowAddress"], tokens))

                con.commit()
            except Exception as e:
                print(e)

    @staticmethod
    def get_functions(model_name: str) -> list:
        functions: list
        with sqlite3.connect('functions.db') as con:
            try:
                cur = con.cursor()
                sql = "SELECT * FROM FUNCTIONS WHERE model_name=?"
                functions = cur.execute(sql, (model_name,)).fetchall()
            except Exception as e:
                print(e)

        return functions

    @staticmethod
    def get_function(model_name: str, function_name: str) -> list:
        function_information: list
        with sqlite3.connect('functions.db') as con:
            try:
                cur = con.cursor()
                sql = "SELECT * FROM FUNCTIONS WHERE model_name=? and function_name=?"
                function_information = cur.execute(
                    sql, (model_name, function_name,)).fetchone()
            except Exception as e:
                print(e)

            return function_information

    @staticmethod
    def delete_functions(model_name: str):
        with sqlite3.connect('functions.db') as con:
            try:
                cur = con.cursor()
                sql = "DELETE FROM FUNCTIONS WHERE model_name=?"
                cur.execute(sql, (model_name,))
                con.commit()
            except Exception as e:
                print(e)

    @staticmethod
    def delete_function(function_name: str):
        with sqlite3.connect('functions.db') as con:
            try:
                cur = con.cursor()
                sql = "DELETE FROM FUNCTIONS WHERE function_name=?"
                cur.execute(sql, (function_name,))
                con.commit()
            except Exception as e:
                print(e)
