import sys
import orjson
import traceback
from typing import TypedDict, Optional
from dataset import DatasetManager
from eda import (
    TierOneEda,
    DatasetOverview,
    MissingInfoSummary,
    NumericalAnalysis,
    CategoricalAnalysis,
    TargetAnalysis,
)
from constants import DATASET_FILE, EDA_METRICS_FILE


class EdaOverview(TypedDict):
    overview: DatasetOverview
    missing_analysis: MissingInfoSummary
    numerical_analysis: NumericalAnalysis
    categorical_analysis: CategoricalAnalysis
    target_analysis: Optional[TargetAnalysis] = None


def main():
    try:
        manager = DatasetManager(DATASET_FILE)
        df = manager.load_dataset()

        eda = TierOneEda(df)

        overview = eda.generate_dataset_overview()
        missing = eda.missing_data_analysis()
        numerical = eda.numerical_analysis()
        categorical = eda.categorical_analysis()

        target_analysis_result = None

        if len(sys.argv) > 1:
            target_col = sys.argv[1]
            if target_col in df.columns:
                target_analysis_result = eda.target_analysis(target_col)

        final_output = EdaOverview(
            overview=overview,
            missing_analysis=missing,
            numerical_analysis=numerical,
            categorical_analysis=categorical,
            target_analysis=target_analysis_result,
        )

        with open(EDA_METRICS_FILE, "wb") as f:
            f.write(
                orjson.dumps(
                    final_output,
                    option=orjson.OPT_SERIALIZE_NUMPY | orjson.OPT_NON_STR_KEYS,
                )
            )
    except Exception:
        print(traceback.format_exc(), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
