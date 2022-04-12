from io import StringIO
import pandas as pd


class TrainingRequest():
    uuid: str
    data: pd.DataFrame

    def __init__(self, uuid: str, data: str):
        self.uuid = uuid
        self.data = self.check_training_data(data)

    def check_training_data(self, data: str) -> pd.DataFrame:
        try:
            contents = StringIO(data)
            df = pd.DataFrame(contents)
            return df
        except Exception as tr_exception:
            raise Exception("invalid dataset") from tr_exception
