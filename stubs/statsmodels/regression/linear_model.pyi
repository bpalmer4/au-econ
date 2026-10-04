from typing import Any

import pandas as pd

class RegressionResults:
    params: pd.Series
    bse: pd.Series
    rsquared: float

class OLS:
    def __init__(self, endog: pd.Series, exog: pd.DataFrame) -> None: ...
    def fit(self, *, cov_type: str = ..., cov_kwds: dict[str, Any] | None = ...) -> RegressionResults: ...
