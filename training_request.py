from asyncio import Future
from io import StringIO
import pandas as pd


class TrainingRequest():
    uuid: str
    data: pd.DataFrame
    status: str

    def __init__(self, uuid: str, data: str):
        self.uuid = uuid
        self.data = self.check_training_data(data)
        self.status = "starting"

    def check_training_data(self, data: str) -> pd.DataFrame:
        try:
            contents = StringIO(data)
            df: pd.DataFrame = pd.DataFrame(contents)
            return df
        except Exception as tr_exception:
            raise Exception("invalid dataset") from tr_exception
