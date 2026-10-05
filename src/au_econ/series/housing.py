"""House prices: a long-run Australian house-price level, spliced from three ABS measures (and BIS before 1986).

The getter is cached for the run and returns copies, so a caller changing a series
cannot corrupt the cache.
"""

from functools import cache
from typing import TYPE_CHECKING

import readabs as ra
from pandas import PeriodIndex
from readabs import metacol as mc

from au_econ.analysis.decompose import seasonally_adjust
from au_econ.series.prices import get_cpi
from au_econ.sources.bis import get_residential_property_prices

if TYPE_CHECKING:
    from pandas import DataFrame, Series

# the discontinued 6416.0 is read from its final (Dec 2021) release page
RPPI_URL = (
    "https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/"
    "residential-property-price-indexes-eight-capital-cities/dec-2021"
)
DWELLINGS_CATALOGUE, DWELLINGS_TABLE = "6432.0", "643201"
RPPI_CATALOGUE, RPPI_TABLE, ESTABLISHED_TABLE = "6416.0", "641601", "641608"
MEAN_PRICE_DID = "Mean price of residential dwellings ;  Australia ;"
RPPI_DID = "Residential Property Price Index ;  Weighted average of eight capital cities ;"
ESTABLISHED_DID = "Price Index of Established Homes ;  Weighted Average of 8 Capital Cities ;"
THOUSAND = 1_000  # 6432.0 mean price is in $'000
BIS_OVERLAP_QUARTERS = 4  # quarters of overlap kept when rebasing the BIS segment onto the ABS level
ORIGINAL, SEASONALLY_ADJUSTED = "Original", "Seasonally Adjusted"


def _quarterly(data: dict[str, DataFrame], meta: DataFrame, selector: dict[str, str]) -> Series:
    """Select one series by description and put it on a Q-DEC index (the tables differ in quarter anchor)."""
    table, series_id, _units = ra.find_abs_id(meta, selector, verbose=False)
    series = data[table][series_id].dropna()
    index = series.index
    if not isinstance(index, PeriodIndex):
        raise TypeError(f"Expected a PeriodIndex for {series_id}")
    series.index = index.asfreq("Q-DEC")
    return series


@cache
def _house_price_index() -> tuple[Series, DataFrame]:
    """Splice the long-run level and keep the splice report (cached; not for mutation)."""
    dwellings, dwellings_meta = ra.read_abs_cat(
        DWELLINGS_CATALOGUE, single_excel_only=DWELLINGS_TABLE, verbose=False
    )
    mean_price = _quarterly(dwellings, dwellings_meta, {MEAN_PRICE_DID: mc.did}) * THOUSAND
    rppi_data, rppi_meta = ra.read_abs_cat(RPPI_CATALOGUE, url=RPPI_URL, verbose=False)
    rppi = _quarterly(rppi_data, rppi_meta, {RPPI_TABLE: mc.table, RPPI_DID: mc.did})
    established = _quarterly(rppi_data, rppi_meta, {ESTABLISHED_TABLE: mc.table, ESTABLISHED_DID: mc.did})
    return ra.splice([mean_price, rppi, established], rebase=True, name="House price index")


@cache
def _spliced(*, extend_bis: bool) -> tuple[Series, DataFrame]:
    """Return the nominal level, optionally extended to 1970Q1 with BIS/REIA (cached; not for mutation).

    The BIS segment is trimmed to BIS_OVERLAP_QUARTERS past the junction: ra.splice() fits one
    factor over the whole overlap, and over forty years the two drift apart enough to invent
    a 2.7 per cent fall at the junction, while one quarter would anchor on a single noisy median.
    """
    abs_level, report = _house_price_index()
    if not extend_bis:
        return abs_level, report
    bis = get_residential_property_prices()
    junction = abs_level.index[0]
    bis = bis[bis.index <= junction + (BIS_OVERLAP_QUARTERS - 1)]
    if bis.index[0] >= junction:
        raise ValueError("The BIS series adds no quarters before the ABS series starts")
    return ra.splice([abs_level, bis], rebase=True, name="Mean dwelling price")


def _deflated(nominal: Series) -> tuple[Series, str]:
    """Deflate by the long-run headline CPI, in the prices of the latest CPI quarter.

    The CPI covers new dwellings and rents, not established houses, so there is no circularity.
    """
    cpi, _units, _stype = get_cpi("headline")
    real = (nominal / (cpi / cpi.iloc[-1])).dropna()
    if real.empty:
        raise ValueError("No overlap between the house-price series and the CPI")
    return real.rename("Real mean dwelling price"), f"$ ({cpi.index[-1]} prices)"


@cache
def _house_prices(*, extend_bis: bool, real: bool, seasonally_adjusted: bool) -> tuple[Series, str, str]:
    """Build the level for one combination of options (cached; not for mutation)."""
    series, _report = _spliced(extend_bis=extend_bis)
    units, stype = "$", ORIGINAL
    if real:
        series, units = _deflated(series)
    if seasonally_adjusted:
        series, stype = seasonally_adjust(series), SEASONALLY_ADJUSTED
    return series, units, stype


def get_house_price_index(
    *, extend_bis: bool = False, real: bool = False, seasonally_adjusted: bool = False
) -> tuple[Series, str, str]:
    """Return (level, units, series type) for a long-run house-price level in dollars, quarterly from 1986Q2.

    Three ABS measures, highest priority first, each rebased onto the running level at its
    overlap: 6432.0 mean price of residential dwellings (all dwellings, from 2011Q3); the
    discontinued 6416.0 RPPI, eight capitals (2003Q3-2021Q4); and its established-house
    index (1986Q2-2005Q2, the pre-2005 method). See get_house_price_splice_report.

    extend_bis splices the BIS index underneath, back to 1970Q1: the 1986 junction is a break
    in method (a REIA median below, a quality-adjusted ABS index above), but where they overlap
    the two agree closely. real deflates by the long-run headline CPI. seasonally_adjusted
    returns the SA component; pass it before indexing the level to any one quarter, or that
    quarter's seasonal factor is baked into the base.
    """
    series, units, stype = _house_prices(extend_bis=extend_bis, real=real, seasonally_adjusted=seasonally_adjusted)
    return series.copy(), units, stype


def get_house_price_splice_report(*, extend_bis: bool = False) -> DataFrame:
    """Return the ra.splice() audit report (rebase factors, junctions); with extend_bis, the ABS-BIS junction."""
    _series, report = _spliced(extend_bis=extend_bis)
    return report.copy()
