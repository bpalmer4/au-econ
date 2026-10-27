"""Long-run labour productivity: GDP per hour worked, spliced back to 1966, and its trend growth.

Two segments: the published National Accounts index (5206.0 Key Aggregates, seasonally
adjusted, unchanged from 1978Q3) over a series derived by dividing seasonally adjusted chain
volume GDP by aggregate weekly hours worked from RBA Occasional Paper 8 table 4.12. Those
hours are an annual August snapshot interpolated to quarters, so the derived segment
contributes growth, not level: the splice rebases it onto the published index.

get_productivity_trend() is trend growth in that index with the COVID swing taken out:
composition lifted GDP per hour in 2020-22 (low-paid hours went first) and took it back.
The log index is joined by a straight line from 2019Q4 to 2023Q1, the two quarters at
which it stood at the same level; the trend is then the compound annual growth rate in the
annual-average level over a trailing window. Trailing, so a published value never revises (unlike a
Henderson or HP trend at the sample end); annual averages, so quarterly noise at the two
ends of a short window does not swing it.
"""

import io
from functools import cache

import numpy as np
import pandas as pd
import readabs as ra
from readabs import metacol as mc

from au_econ.series.gdp import get_gdp, get_table
from au_econ.sources.http_cache import get_file

KEY_AGGREGATES = "5206001_Key_Aggregates"
PRODUCTIVITY_DID = "GDP per hour worked: Index ;"
SA = "Seasonally Adjusted"
INDEX_NUMBERS = "Index Numbers"

# RBA Occasional Paper 8, table 4.12 (Aggregate and Average Weekly Hours Worked). Column 0
# is the calendar year and column 32 the aggregate weekly hours of all employed persons.
# The survey is taken in August.
OP8_HOURS_URL = "https://www.rba.gov.au/statistics/xls/op8/4-12.xls"
OP8_HOURS_SHEET = "4.12"
OP8_HOURS_CACHE_PREFIX = "rba_op8_hours"
OP8_HOURS_YEAR_COL, OP8_HOURS_TOTAL_COL = 0, 32
AUGUST = 8

# --- trend growth
COVID_FLAT_FROM = "2019Q4"
COVID_FLAT_TO = "2023Q1"
TREND_YEARS = 5
QUARTERS_PER_YEAR = 4
LOG_POINTS = 100  # log x 100: changes read as per cent
PERCENT = 100
TREND_UNITS = "Per cent per year"


@cache
def _op8_hours() -> pd.Series:
    """Fetch aggregate weekly hours worked at August each year, on the quarter containing it (cached)."""
    content = get_file(OP8_HOURS_URL, prefix=OP8_HOURS_CACHE_PREFIX)
    raw = pd.read_excel(io.BytesIO(content), sheet_name=OP8_HOURS_SHEET, header=None)
    years = pd.to_numeric(raw[OP8_HOURS_YEAR_COL].astype(str).str.extract(r"^(\d{4})$")[0], errors="coerce")
    hours = pd.to_numeric(raw[OP8_HOURS_TOTAL_COL], errors="coerce")
    keep = years.notna() & hours.notna()
    if not keep.any():
        raise ValueError(f"No aggregate hours worked found in {OP8_HOURS_URL}")
    index = pd.PeriodIndex([pd.Period(year=int(y), month=AUGUST, freq="Q") for y in years[keep]], freq="Q")
    return pd.Series(hours[keep].to_numpy(), index=index, name="Aggregate weekly hours")


def _derived_productivity() -> pd.Series:
    """Return real GDP per aggregate weekly hour, quarterly, on an arbitrary scale.

    The August hours are interpolated (cubic) onto quarters; dividing seasonally adjusted GDP
    by unadjusted hours leaves a level offset that the splice's rebase removes.
    """
    gdp, _units = get_gdp("CVM", "SA")
    hours = _op8_hours()
    quarters = pd.period_range(hours.index[0], hours.index[-1], freq="Q")
    gapped = hours.reindex(quarters)
    gapped.index = quarters.to_timestamp()
    filled = gapped.interpolate(method="cubic")
    filled.index = quarters
    return (gdp / filled).dropna().rename("Derived productivity")


@cache
def _productivity_index() -> tuple[pd.Series, pd.DataFrame]:
    """Splice GDP per hour worked back to 1966, with the splice report (cached; not for mutation)."""
    data, meta = get_table(KEY_AGGREGATES)
    published = ra.select_one(
        data, meta, {KEY_AGGREGATES: mc.table, PRODUCTIVITY_DID: mc.did, SA: mc.stype}
    ).dropna()
    spliced, report = ra.splice([published, _derived_productivity()], rebase=True)
    return spliced.rename("GDP per hour worked"), report


def get_productivity_index() -> tuple[pd.Series, str, str]:
    """Return GDP per hour worked, quarterly from 1966, with its units and series type."""
    spliced, _report = _productivity_index()
    return spliced.copy(), INDEX_NUMBERS, SA


def get_productivity_splice_report() -> pd.DataFrame:
    """Return the ra.splice() audit report for get_productivity_index."""
    return _productivity_index()[1].copy()


@cache
def _productivity_trend(years: int) -> pd.Series:
    """Trend growth in GDP per hour worked, COVID swing flattened (cached; not for mutation)."""
    index, _units, _stype = get_productivity_index()
    log_level = np.log(index) * LOG_POINTS
    start, end = pd.Period(COVID_FLAT_FROM, freq="Q"), pd.Period(COVID_FLAT_TO, freq="Q")
    log_level.loc[(log_level.index > start) & (log_level.index < end)] = np.nan
    flat = log_level.interpolate(method="linear", limit_area="inside")
    annual = flat.rolling(QUARTERS_PER_YEAR).mean()
    log_rate = annual.diff(years * QUARTERS_PER_YEAR) / years
    cagr = (np.exp(log_rate / LOG_POINTS) - 1) * PERCENT
    return cagr.dropna().rename("Productivity trend")


def get_productivity_trend(years: int = TREND_YEARS) -> tuple[pd.Series, str]:
    """Return trend growth in GDP per hour worked, COVID swing flattened, as (series copy, units)."""
    return _productivity_trend(years).copy(), TREND_UNITS
