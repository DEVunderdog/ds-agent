import pandas as pd
import numpy as np
from typing import TypedDict, List, Any


class DatasetShape(TypedDict):
    n_rows: int
    n_columns: int
    memory_mb: float


class DatasetColumnInventory(TypedDict):
    total_columns: int
    numeric_columns: List
    categorical_columns: List
    datetime_columns: List
    boolean_columns: List


class DuplicateRows(TypedDict):
    count: int
    percentage: float


class DatasetOverview(TypedDict):
    shape: DatasetShape
    column_inventory: DatasetColumnInventory
    dtypes_distribution: Any
    duplicate_rows: DuplicateRows


class TierOneEda:
    def __init__(
        self,
        df: pd.DataFrame,
    ):
        self.df = df

    def generate_dataset_overview(self) -> DatasetOverview:
        return DatasetOverview(
            shape=DatasetShape(
                n_rows=len(self.df),
                n_columns=len(self.df.columns),
                memory_mb=self.df.memory_usage(deep=True).sum() / 1024**2,
            ),
            column_inventory=DatasetColumnInventory(
                total_columns=len(self.df.columns),
                numeric_columns=self.df.select_dtypes(
                    include=[np.number]
                ).columns.to_list(),
                categorical_columns=self.df.select_dtypes(
                    include=["object", "category"]
                ).columns.to_list(),
                datetime_columns=self.df.select_dtypes(
                    include=["datetime64"]
                ).columns.to_list(),
                boolean_columns=self.df.select_dtypes(
                    include=["bool"]
                ).columns.to_list(),
            ),
            dtypes_distribution=self.df.dtypes.value_counts().to_dict(),
            duplicate_rows=DuplicateRows(
                count=self.df.duplicated().sum(),
                percentage=(self.df.duplicated().sum() / len(self.df)) * 100,
            ),
        )
