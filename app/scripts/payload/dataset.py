import pandas as pd
from pathlib import Path


class DatasetFileNotFound(Exception):
    pass


class DatasetNotSupported(Exception):
    pass


class DatasetNotLoading(Exception):
    pass


class DatasetManager:
    def __init__(self, file_path: str):
        self.dataset_path = Path(file_path)

        if not self.dataset_path.exists():
            raise DatasetFileNotFound("dataset file not found")

        if self.dataset_path.suffix.lower() != ".csv":
            raise DatasetNotSupported("dataset file is not in .csv format")

    def load_dataset(self):
        try:
            df = pd.read_csv(self.dataset_path)
            return df
        except Exception as e:
            raise DatasetNotLoading(f"error loading dataset: {e}")
