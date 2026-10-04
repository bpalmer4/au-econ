"""Population series wanted by more than one module.

Each getter is cached for the run and returns (series, units), with the series a copy, so
a caller changing it cannot corrupt the cache.
"""

from functools import cache
from typing import TYPE_CHECKING

import readabs as ra
from readabs import metacol as mc

from au_econ.analysis.decompose import decompose
from au_econ.analysis.henderson import hma

if TYPE_CHECKING:
    from pandas import Series

COVID_YEARS = (2020, 2021)  # left out of seasonal estimates
HENDERSON_TERMS = 13
MONTHS_PER_QUARTER = 3

# --- Estimated Resident Population (3101.0): quarterly, persons
ERP_CATALOGUE = "3101.0"
ERP_TABLE = "310104"
ERP_SELECTOR = {
    ";  Australia ;": mc.did,  # the bare name would also match every state's "Australian"
    "Estimated Resident Population ;  Persons ;  ": mc.did,
}


@cache
def _erp() -> tuple[Series, str]:
    """Fetch national ERP (cached; not for mutation)."""
    data, meta = ra.read_abs_cat(ERP_CATALOGUE, single_excel_only=ERP_TABLE, verbose=False)
    _, series_id, units = ra.find_abs_id(meta, ERP_SELECTOR, verbose=False)
    series = data[ERP_TABLE][series_id].dropna()
    if series.empty:
        raise ValueError(f"ABS {ERP_CATALOGUE} returned no national ERP values")
    return series, units


def get_erp(project_quarters: int = 0) -> tuple[Series, str]:
    """National Estimated Resident Population, optionally extended at its latest quarterly growth rate.

    ERP is published about six months after its reference quarter, so a few quarters of
    projection let it divide series that are more current.
    """
    series, units = _erp()
    series = series.copy()
    rate = series.iloc[-1] / series.iloc[-2]
    last = series.index[-1]
    for step in range(1, project_quarters + 1):
        series[last + step] = series[last + step - 1] * rate
    return series, units


# --- smoothing a benchmark-stepped monthly population level
def _complete_trailing_quarter(level: Series) -> Series:
    """Extend a monthly level so its final quarter is complete.

    A quarterly mean of a level estimates the mid-quarter level, so a part-filled final
    quarter would understate the last quarterly increment by a third (one month short) or a
    sixth (two months short). The missing months continue the latest month-on-month rate,
    which is what the ABS's linear interpolation within a benchmark segment publishes next;
    they exist only to centre the quarterly mean. Works on a copy.
    """
    last = level.index[-1]
    missing = (MONTHS_PER_QUARTER - last.month % MONTHS_PER_QUARTER) % MONTHS_PER_QUARTER
    if not missing:
        return level
    level = level.copy()
    rate = level.iloc[-1] / level.iloc[-2]
    for i in range(1, missing + 1):
        level[last + i] = level[last + i - 1] * rate
    return level


def smoothed_monthly_pop_growth(level: Series) -> Series:
    """Turn a benchmark-stepped monthly population level into a smooth monthly increment.

    The ABS interpolates quarterly ERP benchmarks onto months, so the month-on-month change
    of a population level (e.g. the 6202.0 civilian population aged 15+) jumps at each
    benchmark. Differencing first would leave the steps in place, so this works on the
    quarterly trend: complete any part-filled trailing quarter and take quarterly means; take
    the Trend of a multiplicative decomposition, ARIMA extended so the endpoint uses symmetric
    Henderson weights, with the COVID years out of the seasonal estimate; spread each
    quarterly increment evenly over its three months and round the steps with a 13-term
    Henderson moving average; and keep only the months present in the level.
    """
    decomposition = decompose(
        _complete_trailing_quarter(level).resample("Q").mean(),
        model="multiplicative",
        constant_seasonal=True,
        ignore_years=COVID_YEARS,
        arima_extend=True,
    )
    q_trend = decomposition["Trend"]
    monthly = (q_trend.diff() / MONTHS_PER_QUARTER).resample("M").ffill().dropna()
    return hma(monthly, HENDERSON_TERMS).reindex(level.index).dropna()
