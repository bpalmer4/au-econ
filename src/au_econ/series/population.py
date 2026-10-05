"""Population series wanted by more than one module.

Each getter is cached for the run and returns (series, units), with the series a copy, so
a caller changing it cannot corrupt the cache.
"""

from functools import cache
from typing import TYPE_CHECKING

import pandas as pd
import readabs as ra
from pandas import Period, PeriodIndex
from readabs import metacol as mc

from au_econ.analysis.decompose import decompose
from au_econ.analysis.henderson import hma
from au_econ.series.gdp import get_table

if TYPE_CHECKING:
    from pandas import Series

COVID_YEARS = (2020, 2021)  # left out of seasonal estimates
HENDERSON_TERMS = 13
MONTHS_PER_QUARTER = 3

# --- Estimated Resident Population (3101.0): quarterly, persons
ERP_CATALOGUE = "3101.0"
ERP_TABLE = "310104"
ERP_PERSONS = "Estimated Resident Population ;  Persons ;  "
NATIONAL = "Australia"
AGE_TABLE = "3101059"  # Australia, single year of age, June
OPEN_AGE, OPEN_AGE_TEXT = 100, "100 and over"
WORKING_AGE, ADULT_AGE = 15, 21
JUNE = 6
THOUSAND = 1_000.0
PERCENT = 100

# civilian population aged 15+
LFS_CATALOGUE = "6202.0"
CIV15_TABLE = "62020010"
CIV15_DID = "Civilian population aged 15 years and over ;  Persons ;"

# implicit population, from the 5206.0 key aggregates
KEY_AGGREGATES = "5206001_Key_Aggregates"
GDP_CVM_DID = "Gross domestic product: Chain volume measures ;"
GDP_PER_CAPITA_DID = "GDP per capita: Chain volume measures ;"
PER_MILLION = 1_000_000


@cache
def _erp(state: str = NATIONAL) -> tuple[Series, str]:
    """Fetch ERP for Australia or one state, by its full name (cached; not for mutation)."""
    data, meta = ra.read_abs_cat(ERP_CATALOGUE, single_excel_only=ERP_TABLE, verbose=False)
    selector = {
        f";  {state} ;": mc.did,  # the bare name would also match every state's "Australian"
        ERP_PERSONS: mc.did,
    }
    _, series_id, units = ra.find_abs_id(meta, selector, verbose=False)
    series = data[ERP_TABLE][series_id].dropna()
    if series.empty:
        raise ValueError(f"ABS {ERP_CATALOGUE} returned no ERP values for {state}")
    return series, units


def get_state_erp(state: str) -> tuple[Series, str]:
    """Estimated Resident Population of one state or territory, by its full name ("New South Wales")."""
    series, units = _erp(state)
    return series.copy(), units


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


@cache
def _implicit_population() -> tuple[Series, str]:
    """Derive the population implied by the National Accounts (cached; not for mutation)."""
    data, meta = get_table(KEY_AGGREGATES)
    base = {KEY_AGGREGATES: mc.table, "Original": mc.stype}
    _, gdp_id, gdp_units = ra.find_abs_id(meta, base | {GDP_CVM_DID: mc.did}, verbose=False)
    _, per_capita_id, per_capita_units = ra.find_abs_id(meta, base | {GDP_PER_CAPITA_DID: mc.did}, verbose=False)
    if (gdp_units, per_capita_units) != ("$ Millions", "$"):  # the scaling below assumes these
        raise ValueError(f"Implicit population: GDP in {gdp_units!r}, GDP per capita in {per_capita_units!r}")
    table = data[KEY_AGGREGATES]
    population = (table[gdp_id] / table[per_capita_id] * PER_MILLION).dropna()
    if population.empty:
        raise ValueError("Implicit population: no overlapping GDP and GDP per capita")
    return population, "Number"


def get_implicit_population() -> tuple[Series, str]:
    """Return the population implied by the National Accounts: GDP / GDP per capita (CVM, Original), persons.

    National only, quarterly, and as current as the National Accounts.
    """
    series, units = _implicit_population()
    return series.copy(), units


# --- smoothing a benchmark-stepped monthly population level
def complete_trailing_quarter(level: Series) -> Series:
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
        complete_trailing_quarter(level).resample("Q").mean(),
        model="multiplicative",
        constant_seasonal=True,
        ignore_years=COVID_YEARS,
        arima_extend=True,
    )
    q_trend = decomposition["Trend"]
    monthly = (q_trend.diff() / MONTHS_PER_QUARTER).resample("M").ffill().dropna()
    return hma(monthly, HENDERSON_TERMS).reindex(level.index).dropna()


# --- the civilian population aged 15+ (6202.0), monthly
@cache
def _civ15(state: str) -> tuple[Series, str]:
    """Fetch the civilian population aged 15+ for Australia or one state (cached; not for mutation)."""
    data, meta = ra.read_abs_cat(LFS_CATALOGUE, single_excel_only=CIV15_TABLE, verbose=False)
    where = NATIONAL if state == NATIONAL else f"> {state}"  # states are listed as "> New South Wales"
    selector = {CIV15_TABLE: mc.table, CIV15_DID: mc.did, f";  {where} ;": mc.did, "Original": mc.stype}
    _, series_id, units = ra.find_abs_id(meta, selector, verbose=False)
    series = data[CIV15_TABLE][series_id].dropna()
    if series.empty:
        raise ValueError(f"ABS {LFS_CATALOGUE} returned no civilian population aged 15+ for {state}")
    return series, units


def get_civ15(state: str = NATIONAL) -> tuple[Series, str]:
    """Return the civilian population aged 15+ for Australia or one state (full name), monthly, Original ('000).

    It is ERP benchmarks interpolated onto months, so it steps at each benchmark; see
    smoothed_monthly_pop_growth for its growth.
    """
    series, units = _civ15(state)
    return series.copy(), units


# --- single-year-of-age ERP (3101.0), annual at June
@cache
def _erp_age_sum(min_age: int) -> Series:
    """Fetch annual June ERP summed over ages min_age and over (cached; not for mutation)."""
    data, meta = ra.read_abs_cat(ERP_CATALOGUE, single_excel_only=AGE_TABLE, verbose=False)
    persons = meta[meta[mc.did].str.contains("Persons")]
    ids = []
    for _, row in persons.iterrows():
        age_text = str(row[mc.did]).split(";")[2].strip()
        age = OPEN_AGE if age_text == OPEN_AGE_TEXT else int(age_text)
        if age >= min_age:
            ids.append(row[mc.id])
    return data[AGE_TABLE][ids].sum(axis=1).dropna()


def erp_age_sum(min_age: int) -> Series:
    """Return Australia's ERP at June, persons, summed over single years of age min_age and over."""
    return _erp_age_sum(min_age).copy()


def interp_june(annual: Series, index: PeriodIndex) -> Series:
    """Spread an annual June-referenced series onto a quarterly or monthly index.

    Each value is anchored at the June quarter (or month), interpolated linearly between
    anchors, and held flat after the latest.
    """
    freq = index.freqstr
    anchors: dict[Period, float] = {}
    for period, value in annual.items():
        if not isinstance(period, Period):
            raise TypeError("Expected a PeriodIndex on the annual June-referenced series")
        anchor = (
            Period(year=period.year, quarter=2, freq=freq)
            if freq.startswith("Q")
            else Period(year=period.year, month=6, freq=freq)
        )
        anchors[anchor] = float(value)
    return pd.Series(anchors, dtype=float).reindex(index).interpolate(limit_area="inside").ffill()


# --- the population aged 21+, quarterly, built from the civilian population aged 15+
@cache
def _adult_21_share_of_15() -> Series:
    """Fetch the annual June ratio of ERP 21+ to ERP 15+ (cached; not for mutation)."""
    return (_erp_age_sum(ADULT_AGE) / _erp_age_sum(WORKING_AGE)).dropna()


@cache
def _civ15_to_total_upweight() -> Series:
    """Fetch the annual June ratio of total ERP 15+ to the civilian population 15+, about 1.003 (cached).

    It adds back the people the civilian count leaves out, mainly the permanent defence force.
    """
    civ15 = _civ15(NATIONAL)[0] * THOUSAND  # '000 -> persons, monthly
    months = civ15.index
    if not isinstance(months, PeriodIndex):
        raise TypeError("Expected a monthly PeriodIndex for the civilian population")
    june = civ15[months.month == JUNE].copy()
    june.index = months[months.month == JUNE].asfreq("Y-JUN")
    return (_erp_age_sum(WORKING_AGE) / june).dropna()


def interp_21_share(index: PeriodIndex) -> Series:
    """Return the June ratio of ERP 21+ to ERP 15+, spread onto a quarterly or monthly index."""
    return interp_june(_adult_21_share_of_15(), index)


def interp_civ15_to_total(index: PeriodIndex) -> Series:
    """Return the June upweight from the civilian to the total population 15+, spread onto an index."""
    return interp_june(_civ15_to_total_upweight(), index)


@cache
def _adult21() -> tuple[Series, str]:
    """Build the quarterly population aged 21+ (cached; not for mutation)."""
    civ15, units = _civ15(NATIONAL)
    quarterly = ra.monthly_to_qtly(civ15, f="mean")
    quarters = quarterly.index
    if not isinstance(quarters, PeriodIndex):
        raise TypeError("Expected a quarterly PeriodIndex for the civilian population")
    return (interp_21_share(quarters) * interp_civ15_to_total(quarters) * quarterly).dropna(), units


def get_adult21() -> tuple[Series, str]:
    """Return the national population aged 21+, quarterly ('000), approximating the total resident 21+.

    The ABS has no quarterly single-year-of-age population, so this is the quarterly mean
    civilian population 15+ scaled by two June ratios interpolated to quarters: ERP 21+ to
    ERP 15+, and total ERP 15+ to the civilian 15+. Their product anchors the series to the
    resident 21+ population at each June while keeping the smooth Labour Force shape.
    """
    series, units = _adult21()
    return series.copy(), units


@cache
def _smoothed_civ15() -> tuple[Series, Series, str]:
    """Rebuild the civilian 15+ level from its smoothed increment; also return the published level (cached)."""
    published, units = _civ15(NATIONAL)
    increment = smoothed_monthly_pop_growth(published)
    published = published.reindex(increment.index)
    cumulative = increment.cumsum()
    return published.iloc[-1] - (cumulative.iloc[-1] - cumulative), published, units


@cache
def _adult21_monthly() -> tuple[Series, str]:
    """Build the smoothed monthly population aged 21+ (cached; not for mutation)."""
    smoothed, _published, units = _smoothed_civ15()
    months = smoothed.index
    if not isinstance(months, PeriodIndex):
        raise TypeError("Expected a PeriodIndex on the civilian population")
    adults = (smoothed * interp_21_share(months) * interp_civ15_to_total(months)).dropna()
    if adults.empty:
        raise ValueError("No adult population data")
    return adults, units


def get_adult21_monthly() -> tuple[Series, str]:
    """Return the national population aged 21+, monthly and smoothed ('000).

    The civilian 15+ level is rebuilt from its smoothed monthly increment (so without the
    steps at each ERP benchmark), anchored at the latest published month, then scaled to the
    total resident 21+ by the same two interpolated June ratios as get_adult21.
    """
    series, units = _adult21_monthly()
    return series.copy(), units


def get_smoothed_civ15_gap() -> float:
    """Return the largest gap (%) between the smoothed civilian 15+ level and the published one."""
    smoothed, published, _units = _smoothed_civ15()
    return float(((smoothed / published - 1) * PERCENT).abs().max())
