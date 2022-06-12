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
        with sqlite3.connect('models.db') as con:
            try:
                cur = con.cursor()
                sql = "SELECT * FROM MODELS"
                models = cur.execute(sql).fetchall()
                for model in models:
                    models_set.add(model[0])

                return models_set
            except Exception as e:
                print(e)

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
                cur = con.cursor()
                sql = "DELETE FROM MODELS WHERE model_name=?"
                cur.execute(sql, (model_name,))
                con.commit()
            except Exception as e:
                print(e)
