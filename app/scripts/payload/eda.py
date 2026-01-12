import pandas as pd
import numpy as np
from scipy import stats
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


class MissingInfo(TypedDict):
    column: Any
    missing_count: int
    missing_percentage: float
    dtype: Any


class MissingCorrelations(TypedDict):
    column_a: Any
    column_b: Any
    correlation: Any


class MissingInfoSummary(TypedDict):
    column_wise_missing: List[MissingInfo]
    missing_correlations: List[MissingCorrelations]
    total_missing_cells: int
    number_of_columns_with_missing_values: int


class NormalityChecks(TypedDict):
    is_normal: bool
    p_value: float
    interpretation: str


class BasicColumnNumericalStats(TypedDict):
    count: int
    mean: float
    median: float
    std: float
    min: float
    max: float
    q1: float
    q3: float
    iqr: float


class IqrMethodOutlier(TypedDict):
    count: float
    percentage: float
    lower_bound: float
    upper_bound: float


class ZScoreMethodOutlier(TypedDict):
    count: float
    percentage: float


class OutliersInfo(TypedDict):
    iqr_based: IqrMethodOutlier
    zscore_based: ZScoreMethodOutlier


class ColumnDistribution(TypedDict):
    skewness: float
    kurtosis: float
    normality: NormalityChecks
    unique_values: Any
    unique_percentage: float


class CorrelationNumericalAnalysis(TypedDict):
    feature_one: Any
    feature_two: Any
    correlation_value: float


class ZerosAndConstants(TypedDict):
    zero_count: int
    zero_appearance_percentage: float
    is_constant: bool


class ColumnNumericalAnalysis(TypedDict):
    column: str
    basic_stats: BasicColumnNumericalStats
    distribution: ColumnDistribution
    outliers: OutliersInfo
    zeros_and_constants: ZerosAndConstants


class NumericalAnalysis(TypedDict):
    column_analysis: ColumnNumericalAnalysis
    correlation_matrix: Any
    correlations: CorrelationNumericalAnalysis


class CategoricalCardinality(TypedDict):
    unique_values: int
    cardinality_ratio: float


class CategoricalDistribution(TypedDict):
    top_5_values: Any
    top_value_frequency: float
    entropy: float


class CategoricalBalance(TypedDict):
    is_balance: bool
    imbalance_ratio: float


class CategoricalAnalysis(TypedDict):
    column: str
    cardinality: CategoricalCardinality
    categorical_distribution: CategoricalDistribution
    balance: CategoricalBalance


class CramersMatrix(TypedDict):
    feature_one: Any
    feature_two: Any
    cramers_v: float


class AnovaResults(TypedDict):
    f_statistic: float
    p_value: float
    significant: bool


class RelationshipAnalysis(TypedDict):
    pass


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

    def check_missing_correlation(self) -> List[MissingCorrelations]:
        missing_df = self.df.isnull().astype(int)
        corr_matrix = missing_df.corr()

        high_correlations: List[MissingCorrelations] = []
        for i in range(len(corr_matrix.columns)):
            for j in range(i + 1, len(corr_matrix.columns)):
                if abs(corr_matrix.iloc[i, j]) > 0.5:
                    high_correlations.append(
                        MissingCorrelations(
                            column_a=corr_matrix.columns[i],
                            column_b=corr_matrix.columns[j],
                            correlation=corr_matrix.iloc[i, j],
                        ),
                    )

        return high_correlations

    def missing_data_analysis(self):
        missing_stats: List[MissingInfo] = []

        for col in self.df.columns:
            missing_count = self.df[col].isnull().sum()
            missing_percentage = (missing_count / len(self.df)) * 100

            if missing_count > 0:
                missing_info = MissingInfo(
                    column=col,
                    missing_count=missing_count,
                    missing_percentage=missing_percentage,
                    dtype=str(self.df[col].dtype),
                )
                missing_stats.append(missing_info)

        missing_correlations = self.check_missing_correlation()

        return MissingInfoSummary(
            column_wise_missing=missing_stats,
            missing_correlations=missing_correlations,
            total_missing_cells=self.df.isnull().sum().sum(),
            number_of_columns_with_missing_values=len(
                [col for col in self.df.columns if self.df[col].isnull().any()]
            ),
        )

    def check_normality(self, series: pd.Series) -> NormalityChecks:
        sample = series.dropna().sample(min(5000, len(series)))

        if len(sample) < 3:
            return {
                "test": "insufficient data",
            }

        _, p_value = stats.shapiro(sample)

        return NormalityChecks(
            is_normal=p_value > 0.05,
            p_value=p_value,
            interpretation="normal" if p_value > 0.05 else "non-normal",
        )

    def detect_outliers(self, series: pd.Series) -> OutliersInfo:
        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)

        iqr = q3 - q1

        iqr_outliers = ((series < (q1 - 1.5 * iqr)) | (series > (q3 + 1.5 * iqr))).sum()

        z_scores = np.abs((series - series.mean()) / series.std())
        z_outliers = (z_scores > 3).sum()

        return OutliersInfo(
            iqr_based=IqrMethodOutlier(
                count=iqr_outliers,
                percentage=(iqr_outliers / len(series)) * 100,
                lower_bound=q1 - 1.5 * iqr,
                upper_bound=q3 + 1.5 * iqr,
            ),
            zscore_based=ZScoreMethodOutlier(
                count=z_outliers,
                percentage=(z_outliers / len(series)) * 100,
            ),
        )

    def find_high_correlation(
        self, threshold: float = 0.6
    ) -> List[CorrelationNumericalAnalysis]:
        corr_matrix = self.df.corr()

        high_corr: List[CorrelationNumericalAnalysis] = []

        for i in range(len(corr_matrix.columns)):
            for j in range(i + 1, len(corr_matrix.columns)):
                if abs(corr_matrix.iloc[i, j]) > threshold:
                    high_corr.append(
                        CorrelationNumericalAnalysis(
                            feature_one=corr_matrix.columns[i],
                            feature_two=corr_matrix.columns[j],
                            correlation_value=corr_matrix.iloc[i, j],
                        )
                    )

        return high_corr

    def numerical_analysis(self) -> NumericalAnalysis:
        numeric_cols = self.df.select_dtypes(include=[np.number]).columns

        analysis: List[NumericalAnalysis] = []

        for col in numeric_cols:
            col_analysis = ColumnNumericalAnalysis(
                column=col,
                basic_stats=BasicColumnNumericalStats(
                    count=self.df[col].count(),
                    mean=self.df[col].mean(),
                    median=self.df[col].median(),
                    std=self.df[col].std(),
                    min=self.df[col].min(),
                    max=self.df[col].max(),
                    q1=self.df[col].quantile(0.25),
                    q3=self.df[col].quantile(0.75),
                    iqr=self.df[col].quantile(0.75) - self.df[col].quantile(0.25),
                ),
                distribution=ColumnDistribution(
                    skewness=self.df[col].skew(),
                    kurtosis=self.df[col].kurtosis(),
                    normality=self.check_normality(series=self.df[col]),
                    unique_values=self.df[col].nunique(),
                    unique_percentage=(self.df[col].nunique() / len(self.df)) * 100,
                ),
                outliers=self.detect_outliers(self.df[col]),
                zeros_and_constants=ZerosAndConstants(
                    zero_count=(self.df[col] == 0).sum(),
                    zero_appearance_percentage=(
                        (self.df[col] == 0).sum() / len(self.df)
                    )
                    * 100,
                    is_constant=self.df[col].nunique() == 1,
                ),
            )
            analysis.append(col_analysis)

        return NumericalAnalysis(
            column_analysis=analysis,
            correlation_matrix=self.df[numeric_cols].corr().to_dict(),
            correlations=self.find_high_correlation(),
        )

    def calculate_entropy(self, series: pd.Series):
        value_counts = series.value_counts(normalize=True)
        return -np.sum(value_counts * np.log2(value_counts + 1e-10))

    def check_categorical_balance(
        self,
        value_counts,
    ):
        max_freq = value_counts.max()
        min_freq = value_counts.min()

        return (max_freq / min_freq) < 5 if min_freq > 0 else False

    def categorical_analysis(self):
        categorical_cols = self.df.select_dtypes(include=["object", "category"]).columns

        analysis: List[CategoricalAnalysis] = []

        for col in categorical_cols:
            value_counts = self.df[col].value_counts()

            col_analysis = CategoricalAnalysis(
                column=col,
                cardinality=CategoricalCardinality(
                    unique_values=self.df[col].nunique(),
                    cardinality_ratio=self.df[col].nunique() / len(self.df),
                ),
                categorical_distribution=CategoricalDistribution(
                    top_5_values=value_counts.head(5).to_dict(),
                    top_value_frequency=(
                        value_counts.iloc[0] / len(self.df) * 100
                        if len(value_counts) > 0
                        else 0
                    ),
                    entropy=self.calculate_entropy(self.df[col]),
                ),
                balance=CategoricalBalance(
                    is_balance=self.check_categorical_balance(
                        value_counts=value_counts
                    ),
                    imbalance_ratio=(
                        value_counts.max() / value_counts.min()
                        if value_counts.min() > 0
                        else float("inf")
                    ),
                ),
            )

            analysis.append(col_analysis)

        return {
            "categorical_analysis": analysis,
        }

    def calculate_cramers_v_matrix(self, categorical_cols):
        associations: List[CramersMatrix] = []

        for i, col1 in enumerate(categorical_cols):
            for col2 in categorical_cols[i + 1 :]:
                contingency = pd.crosstab(self.df[col1], self.df[col2])
                chi2, _, _, _ = stats.chi2_contingency(contingency)
                n = contingency.sum().sum()
                cramers_v = np.sqrt(chi2 / (n * (min(contingency.shape) - 1)))

                if cramers_v > 0.3:
                    associations.append(
                        CramersMatrix(
                            feature_one=col1,
                            feature_two=col2,
                            cramers_v=cramers_v,
                        )
                    )

        return associations

    def calculate_anove(
        self, numeric_feature: Any, categorical_target: Any
    ) -> AnovaResults:

        data = self.df[[numeric_feature, categorical_target]].dropna()

        groups = [
            group[numeric_feature].values
            for name, group in data.groupby(categorical_target)
        ]

        if len(groups) < 2:
            return None

        f_stat, p_value = stats.f_oneway(*groups)

        return AnovaResults(
            f_statistic=float(f_stat),
            p_value=float(p_value),
            significant=float(p_value) < 0.05,
        )

    def calculate_chi_square(self, categorical_feature, categorical_target):
        contingency_table = pd.crosstab(self.df[categorical_feature], self.df[categorical_target])

        if (
            contingency_table.empty
            or contingency_table.shape[0] < 2
            or contingency_table.shape[1] < 2
        ):
            return None

        chi2, p, dof, expected = stats.chi2_contingency(contingency_table)

        return {
            "chi2_statistic": float(chi2),
            "p_value": float(p),
            "degrees_of_freedom": int(dof),
            "significant": float(p) < 0.05,
        }

    def calculate_eta_squared(self, categorical_feature, numeric_target):

        data = self.df[[categorical_feature, numeric_target]].dropna()
        
        grand_mean = data[numeric_target].mean()
        
        groups = data.groupby(categorical_feature)[numeric_target]
        
        ssb = sum(groups.count() * (groups.mean() - grand_mean)**2)
        
        sst = sum((data[numeric_target] - grand_mean)**2)
        
        if sst == 0:
            return 0.0
            
        eta_squared = ssb / sst
        
        return {
            "value": float(eta_squared),
        }