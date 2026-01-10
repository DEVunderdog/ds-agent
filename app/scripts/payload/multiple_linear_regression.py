import pandas as pd
import numpy as np
from typing import TypedDict
from sklearn.model_selection import train_test_split, cross_validate
from sklearn.dummy import DummyRegressor
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
from typing import Any


class BasicEvalMetrics(TypedDict):
    model: str
    mean_absolute_error: float
    root_mean_squared_error: float
    r2_score: float


class MeanStdEval(TypedDict):
    mean: float
    std: float


class CrossValidateEval(TypedDict):
    model: str
    mean_absolute_error: MeanStdEval
    root_mean_squared_error: MeanStdEval
    r2_score: MeanStdEval


class MultipleLinearRegression:
    def __init__(
        self,
        test_size: float = 0.2,
        random_state: int = 42,
    ):
        self.test_size = test_size
        self.random_state = random_state

        self.x_train = None
        self.x_test = None
        self.y_train = None
        self.y_test = None

        self.baseline_model = None

    def load_and_split_data(self, x: pd.DataFrame, y: pd.Series) -> None:
        self.x_train, self.x_test, self.y_train, self.y_test = train_test_split(
            x,
            y,
            test_size=self.test_size,
            random_state=self.random_state,
        )

    def build_baseline_model(self, strategy: str = "mean") -> None:
        self.baseline_model = DummyRegressor(strategy=strategy)
        self.baseline_model.fit(self.x_train, self.y_train)

    def _evaluate_model(
        self, model: Any, name: str, predictions_inputs: Any, reference: Any
    ) -> BasicEvalMetrics:
        predictions = model.predict(predictions_inputs)

        mse = mean_squared_error(reference, predictions)
        rmse = np.sqrt(mse)
        mae = mean_absolute_error(reference, predictions)
        r2 = r2_score(reference, predictions)

        return BasicEvalMetrics(
            model=name,
            mean_absolute_error=round(mae, 4),
            root_mean_squared_error=round(rmse, 4),
            r2_score=round(r2, 4),
        )

    def calculate_cross_validation_eval(
        self,
        name: str,
        model: Any,
        x: Any,
        y: Any,
        cv: int = 5,
    ):
        results = cross_validate(
            model=model,
            X=x,
            y=y,
            cv=cv,
            scoring=["r2", "neg_mean_absolute_error", "neg_root_mean_squared_error"],
            return_train_score=True,
        )

        r2_scores = results["test_r2"]
        mae_scores = -results["test_neg_mean_absolute_error"]
        rmse_scores = -results["test_neg_root_mean_squared_error"]

        return CrossValidateEval(
            model=name,
            mean_absolute_error=MeanStdEval(
                mean=format(mae_scores.mean(), ".4f"),
                std=format(mae_scores.std(), ".4f"),
            ),
            root_mean_squared_error=MeanStdEval(
                mean=format(rmse_scores.mean(), ".4f"),
                std=format(rmse_scores.std(), ".4f"),
            ),
            r2_score=MeanStdEval(
                mean=format(r2_scores.mean(), ".4f"),
                std=format(r2_scores.std(), ".4f"),
            ),
        )