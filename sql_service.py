import os
import sqlite3


class SQLUtil():

    @staticmethod
    def save_model(model_name: str, model: bytes):
        with sqlite3.connect('models.db') as con:
            try:
                cur = con.cursor()
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS models(model_name VARCHAR(64), model BLOB)")

                sql = "INSERT INTO models (model_name, model) VALUES (?, ?)"
                cur.execute(sql, (model_name, sqlite3.Binary(model)))
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
        with sqlite3.connect('models.db') as con:
            try:
                cur = con.cursor()
                sql = "SELECT * FROM MODELS WHERE model_name=?"
                model = cur.execute(sql, (model_name,)).fetchone()
                return model
            except Exception as e:
                print(e)

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
    def save_functions(model_name: str, functions: dict):
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
    def get_functions(model_name: str) -> set:
        with sqlite3.connect('functions.db') as con:
            try:
                cur = con.cursor()
                sql = "SELECT * FROM FUNCTIONS WHERE model_name=?"
                functions: list = cur.execute(sql, (model_name,)).fetchall()
                return functions
            except Exception as e:
                print(e)

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
