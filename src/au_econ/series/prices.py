"""Price and wage indexes: CPI measures, the Living Cost Index, WPI, AWOTE, National Accounts deflators.

Each getter is cached for the run and returns (series, units, series type), with the
series a copy, so a caller changing it cannot corrupt the cache.
"""

from functools import cache
from typing import TYPE_CHECKING

import pandas as pd
import readabs as ra
from readabs import metacol as mc

from au_econ.series.gdp import get_table

if TYPE_CHECKING:
    from pandas import Series

# --- CPI (6401.0): seasonally adjusted measures from the analytical appendix table
CPI_CATALOGUE = "6401.0"
CPI_APPENDIX_TABLE = "64010Appendix1a"
CPI_MEASURES = {
    "headline_sa": "Index Numbers ;  All groups CPI, seasonally adjusted ;  Australia ;",
    "trimmed": "Index Numbers ;  Trimmed Mean ;  Australia ;",
    "weighted": "Index Numbers ;  Weighted Median ;  Australia ;",
}
SEASONALLY_ADJUSTED = "Seasonally Adjusted"
INDEX_NUMBERS = "Index Numbers"
# the long-run headline index, rebuilt from the quarterly table
HEADLINE = "headline"
CPI_QUARTERLY_TABLE = "6401017"
CPI_CHANGE_DID = "Percentage Change from Previous Period ;  All groups CPI ;  Australia ;"
CPI_INDEX_DID = "Index Numbers ;  All groups CPI ;  Australia ;"
PERCENT = 100

# --- Living Cost Index (6467.0): employee households
LCI_CATALOGUE = "6467.0"
LCI_TABLE = "646701"
LCI_SELECTOR = {"Index Numbers": mc.did, "Employee households": mc.did, "All groups": mc.did}

# --- wages: WPI (6345.0) and AWOTE (6302.0)
WPI_CATALOGUE, WPI_TABLE = "6345.0", "634501"
WPI_DID = (
    "Quarterly Index ;  Total hourly rates of pay excluding bonuses ;  "
    "Australia ;  Private and Public ;  All industries ;"
)
AWOTE_CATALOGUE, AWOTE_TABLE = "6302.0", "6302003"
AWOTE_DID = "Earnings; Persons; Full Time; Adult; Ordinary time earnings ;"
ORIGINAL = "Original"


@cache
def _cpi(measure: str) -> tuple[Series, str, str]:
    """Fetch one seasonally adjusted CPI index (cached; not for mutation)."""
    data, meta = ra.read_abs_cat(CPI_CATALOGUE, single_excel_only=CPI_APPENDIX_TABLE, verbose=False)
    selector = {
        CPI_APPENDIX_TABLE: mc.table,
        CPI_MEASURES[measure]: mc.did,
        SEASONALLY_ADJUSTED: mc.stype,
        INDEX_NUMBERS: mc.unit,
    }
    table, series_id, units = ra.find_abs_id(meta, selector, verbose=False)
    series = data[table][series_id].dropna()
    if series.empty:
        raise ValueError(f"CPI {measure}: no data in {CPI_APPENDIX_TABLE}")
    return series, units, SEASONALLY_ADJUSTED


@cache
def _cpi_headline() -> tuple[Series, str, str]:
    """Rebuild the long-run headline CPI from 1948Q4 (cached; not for mutation).

    The published early index is rounded to few figures, which puts steps into any growth
    taken from it; the published quarterly change is finer. So the change is chained into a
    relative index and rebased onto the published index at the latest common quarter: a
    smooth index on the current ABS reference base.
    """
    data, meta = ra.read_abs_cat(CPI_CATALOGUE, single_excel_only=CPI_QUARTERLY_TABLE, verbose=False)
    base = {CPI_QUARTERLY_TABLE: mc.table, ORIGINAL: mc.stype, "Quarter": mc.freq}
    _, change_id, _ = ra.find_abs_id(meta, base | {CPI_CHANGE_DID: mc.did, "Percent": mc.unit}, verbose=False)
    _, index_id, _ = ra.find_abs_id(meta, base | {CPI_INDEX_DID: mc.did, INDEX_NUMBERS: mc.unit}, verbose=False)
    change = data[CPI_QUARTERLY_TABLE][change_id].dropna() / PERCENT
    published = data[CPI_QUARTERLY_TABLE][index_id].dropna()
    relative = (1 + change).cumprod()
    anchor = relative.index.intersection(published.index)[-1]
    index = relative / relative.loc[anchor] * published.loc[anchor]
    return index.rename("Headline CPI (reconstructed)"), INDEX_NUMBERS, ORIGINAL


def get_cpi(measure: str) -> tuple[Series, str, str]:
    """Return a quarterly CPI index: "headline" (Original, from 1948Q4), "headline_sa", "trimmed", "weighted"."""
    if measure == HEADLINE:
        series, units, stype = _cpi_headline()
    elif measure in CPI_MEASURES:
        series, units, stype = _cpi(measure)
    else:
        raise ValueError(f"Unknown CPI measure {measure!r}; choose from {(HEADLINE, *CPI_MEASURES)}")
    return series.copy(), units, stype


# --- monthly headline CPI, seasonally adjusted, spliced back before the monthly CPI began
CPI_MONTHLY_TABLE = "640106"
CPI_INDICATOR_CATALOGUE, CPI_INDICATOR_TABLE = "6484.0", "648401"  # the discontinued Monthly CPI Indicator
CPI_INDICATOR_URL = (
    "https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/"
    "monthly-consumer-price-index-indicator/latest-release"
)
QTR_END_TO_MID = 1  # months from the last month of a quarter back to its middle month


@cache
def _monthly_cpi() -> tuple[Series, pd.DataFrame]:
    """Splice the monthly SA headline CPI and return it with the splice report (cached; not for mutation)."""
    selector = {CPI_MEASURES["headline_sa"]: mc.did, SEASONALLY_ADJUSTED: mc.stype, "Month": mc.freq}
    current, current_meta = ra.read_abs_cat(CPI_CATALOGUE, single_excel_only=CPI_MONTHLY_TABLE, verbose=False)
    indicator, indicator_meta = ra.read_abs_cat(
        CPI_INDICATOR_CATALOGUE, url=CPI_INDICATOR_URL, single_excel_only=CPI_INDICATOR_TABLE, verbose=False
    )
    monthly, discontinued = ra.select([(current, current_meta, selector), (indicator, indicator_meta, selector)])

    # qtly_to_monthly places each quarter on its last month; a quarterly index is a quarter
    # average, so it belongs on the middle month.
    quarterly, _units, _stype = _cpi("headline_sa")
    interpolated = ra.qtly_to_monthly(quarterly, interpolate=True)
    interpolated.index = interpolated.index - QTR_END_TO_MID

    cpi, report = ra.splice([monthly, discontinued, interpolated], rebase=True)
    if cpi.empty or cpi.isna().any():
        raise ValueError("The spliced monthly CPI is empty or has gaps")
    return cpi, report


def get_monthly_cpi() -> tuple[Series, str, str]:
    """Return a monthly headline CPI, seasonally adjusted, on the current monthly CPI's reference base.

    Segments, highest priority first: the monthly CPI (6401.0 table 640106), the discontinued
    Monthly CPI Indicator (6484.0), and the quarterly SA CPI interpolated onto middle months.
    Spliced with rebase=True, as an index across reference-period changes.
    """
    series, _report = _monthly_cpi()
    return series.copy(), INDEX_NUMBERS, SEASONALLY_ADJUSTED


def get_monthly_cpi_splice_report() -> pd.DataFrame:
    """Return the ra.splice() audit report for get_monthly_cpi."""
    return _monthly_cpi()[1].copy()


@cache
def _living_cost_index() -> tuple[Series, str, str]:
    """Fetch the employee households Living Cost Index (cached; not for mutation)."""
    data, meta = ra.read_abs_cat(LCI_CATALOGUE, get_zip=False, get_excel=True)
    table, series_id, units = ra.find_abs_id(meta, {LCI_TABLE: mc.table} | LCI_SELECTOR)
    series = data[table][series_id]
    if series.dropna().empty:
        raise ValueError(f"LCI: no data in {LCI_TABLE}")
    stype = str(meta.loc[meta[mc.id] == series_id, mc.stype].iloc[0])
    return series, units, stype


def get_living_cost_index() -> tuple[Series, str, str]:
    """Return the quarterly Living Cost Index for employee households (All groups)."""
    series, units, stype = _living_cost_index()
    return series.copy(), units, stype


@cache
def _wpi() -> tuple[Series, str, str]:
    """Fetch the Wage Price Index, seasonally adjusted (cached; not for mutation)."""
    data, meta = ra.read_abs_cat(WPI_CATALOGUE, single_excel_only=WPI_TABLE, verbose=False)
    selector = {WPI_TABLE: mc.table, WPI_DID: mc.did, SEASONALLY_ADJUSTED: mc.stype, INDEX_NUMBERS: mc.unit}
    table, series_id, units = ra.find_abs_id(meta, selector, verbose=False)
    return data[table][series_id], units, SEASONALLY_ADJUSTED


@cache
def _awote() -> tuple[Series, str, str]:
    """Fetch AWOTE, Original, moved onto December-ending quarters (cached; not for mutation).

    Published every six months (May and November) on a Q-NOV index; reinterpreted onto Q-DEC
    so it aligns with other quarterly series. Matched exactly, so it does not also pick up
    the standard-error series.
    """
    data, meta = ra.read_abs_cat(AWOTE_CATALOGUE, single_excel_only=AWOTE_TABLE, verbose=False)
    selector = {AWOTE_TABLE: mc.table, AWOTE_DID: mc.did, ORIGINAL: mc.stype}
    table, series_id, units = ra.find_abs_id(meta, selector, exact_match=True, verbose=False)
    series = data[table][series_id].dropna()
    series.index = pd.PeriodIndex(series.index, freq="Q-DEC")
    return series, units, ORIGINAL


def get_wage_index(measure: str = "WPI") -> tuple[Series, str, str]:
    """Return a wage measure: "WPI" (SA quarterly index, 6345.0) or "AWOTE" (Original $/week, 6302.0)."""
    if measure == "WPI":
        series, units, stype = _wpi()
    elif measure == "AWOTE":
        series, units, stype = _awote()
    else:
        raise ValueError(f"Unknown wage measure {measure!r}: choose from ('WPI', 'AWOTE')")
    return series.copy(), units, stype


# --- National Accounts implicit price deflators (5206.0), published seasonally adjusted only
DEFLATOR_TABLE = "5206005_Expenditure_Implicit_Price_Deflators"
DEFLATOR_DIDS = {
    "DFD": "Domestic final demand ;",
    "GNE": "Gross national expenditure ;",
    "HFCE": "Households ;  Final consumption expenditure ;",
    "GDP": "GROSS DOMESTIC PRODUCT ;",
}


@cache
def _price_deflator(measure: str) -> tuple[Series, str, str]:
    """Fetch one implicit price deflator index (cached; not for mutation)."""
    data, meta = get_table(DEFLATOR_TABLE)
    selector = {
        DEFLATOR_TABLE: mc.table,
        DEFLATOR_DIDS[measure]: mc.did,
        SEASONALLY_ADJUSTED: mc.stype,
        INDEX_NUMBERS: mc.unit,
    }
    table, series_id, units = ra.find_abs_id(meta, selector, verbose=False)
    series = data[table][series_id]
    if series.dropna().empty:
        raise ValueError(f"Deflator {measure}: no data in {DEFLATOR_TABLE}")
    return series, units, SEASONALLY_ADJUSTED


def get_price_deflator(measure: str = "DFD") -> tuple[Series, str, str]:
    """Return an implicit price deflator index: "DFD" (domestic final demand), "GNE", "HFCE" or "GDP".

    The GDP deflator embeds export prices, so it is a poor domestic gauge when the terms
    of trade move; domestic final demand is the default.
    """
    if measure not in DEFLATOR_DIDS:
        raise ValueError(f"Unknown deflator {measure!r}; choose from {tuple(DEFLATOR_DIDS)}")
    series, units, stype = _price_deflator(measure)
    return series.copy(), units, stype
