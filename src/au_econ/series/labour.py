"""Labour market series wanted by more than one module: the long-run unemployment rate.

get_unemployment_rate() splices one monthly rate back to 1950 from three segments, highest
priority first: the published Labour Force Survey rate (6202.0, monthly from February 1978),
the ABS Modellers' Database rate (1364.0.15.003, quarterly counts turned into a rate and
interpolated to monthly, from 1959Q3), and a backcast from the CES registered unemployment
rate (RBA Occasional Paper 8 table 4.15), fitted to the survey over 1960-1970. Rebasing is
off: these are rates, not index levels.

The pre-survey segment is an estimate, not an observation: a straight line fitted over ten
years of overlap and applied to earlier years. get_unemployment_backcast_stats() returns the
fit diagnostics, and get_unemployment_splice_report() the ra.splice() audit; read them
before leaning on the 1950s. There is a real two-month gap at 1959-07/08 between the
backcast and the Modellers' Database, which the splice leaves rather than interpolating.
"""

import io
from functools import cache

import numpy as np
import pandas as pd
import readabs as ra
from readabs import metacol as mc

from au_econ.sources.http_cache import get_file

# --- segments
MODELLERS_CATALOGUE, MODELLERS_TABLE = "1364.0.15.003", "1364015003"
LFS_CATALOGUE, LFS_TABLE = "6202.0", "62020001"
LFS_SELECTOR = {
    LFS_TABLE: mc.table,
    "Unemployment rate ;  Persons ;": mc.did,
    "Seasonally Adjusted": mc.stype,
    "Percent": mc.unit,
}

# RBA Occasional Paper 8, table 4.15 (Unemployment). Column 38 is the CES registered
# unemployment rate; column 0 is the financial year, labelled by its end year. Data start on
# row 9. Table note (b): the CES count is taken at the end of June each year.
OP8_URL = "https://www.rba.gov.au/statistics/xls/op8/4-15.xls"
OP8_SHEET = "4.15"
OP8_CACHE_PREFIX = "rba_op8"
OP8_FIRST_DATA_ROW = 9
OP8_YEAR_COL, OP8_CES_RATE_COL = 0, 38

JUNE = 6
CALIBRATION_YEARS = (1960, 1970)  # financial years used to fit the CES-to-survey relationship
UNITS, STYPE = "Percent", "Seasonally Adjusted"


@cache
def _ces_rate() -> pd.Series:
    """CES registered unemployment rate at end-June each year, on June months (cached; not for mutation).

    Registered unemployment is not the survey concept: it counts people who signed on with
    the CES seeking full-time work.
    """
    content = get_file(OP8_URL, prefix=OP8_CACHE_PREFIX)
    raw = pd.read_excel(io.BytesIO(content), sheet_name=OP8_SHEET, header=None)
    table = raw.loc[OP8_FIRST_DATA_ROW:, [OP8_YEAR_COL, OP8_CES_RATE_COL]].copy()
    table.columns = ["year", "rate"]
    # the year column also holds footnote markers and trailing note text
    table["year"] = pd.to_numeric(table["year"].astype(str).str.extract(r"(\d{4})")[0], errors="coerce")
    table["rate"] = pd.to_numeric(table["rate"], errors="coerce")
    table = table.dropna()
    if table.empty:
        raise ValueError(f"No CES unemployment data found in {OP8_URL}")
    index = pd.PeriodIndex([pd.Period(year=int(y), month=JUNE, freq="M") for y in table["year"]], freq="M")
    return pd.Series(table["rate"].to_numpy(), index=index, name="CES registered")


@cache
def _modellers_rate() -> pd.Series:
    """Monthly unemployment rate from the Modellers' Database, from 1959Q3 (cached; not for mutation).

    The database publishes quarterly seasonally adjusted counts rather than the rate, so the
    rate is computed from them, then interpolated to monthly. The survey was itself
    quarterly until February 1978, so the monthly detail is filled in, not surveyed.
    """
    data, meta = ra.read_abs_cat(MODELLERS_CATALOGUE, single_excel_only=MODELLERS_TABLE, verbose=False)
    unemployed, labour_force = ra.select(
        [
            (data, meta, {MODELLERS_TABLE: mc.table, "Total unemployed ;": mc.did}),
            (data, meta, {MODELLERS_TABLE: mc.table, "Total labour force ;": mc.did}),
        ]
    )  # both are SA counts in '000, so the unit-coherence check passes
    quarterly = (unemployed / labour_force * 100).dropna()
    return ra.qtly_to_monthly(quarterly).rename("Modellers' Database")


@cache
def _lfs_rate() -> pd.Series:
    """Monthly LFS unemployment rate, seasonally adjusted, as published (cached; not for mutation)."""
    data, meta = ra.read_abs_cat(LFS_CATALOGUE, single_excel_only=LFS_TABLE, verbose=False)
    return ra.select_one(data, meta, LFS_SELECTOR).dropna().rename("Labour Force Survey")


def _june_pairs(
    ces: pd.Series, modellers: pd.Series, window: tuple[int, int]
) -> tuple[pd.DataFrame, pd.Period, str]:
    """Pair the CES rate with the survey rate at June, inside the fitting window.

    Both sides are taken at June because the CES count is an end-June snapshot; fitting it
    against a financial-year average produces a spurious one-year lag. Returns the pairs, the
    survey's first June and the survey's frequency string.
    """
    index = modellers.index
    if not isinstance(index, pd.PeriodIndex):
        raise TypeError(f"modellers must have a PeriodIndex, got {type(index).__name__}")
    june = modellers[index.month == JUNE]
    paired = pd.DataFrame({"survey": june, "ces": ces}).dropna()
    paired_index = paired.index
    if not isinstance(paired_index, pd.PeriodIndex):
        raise TypeError(f"paired must have a PeriodIndex, got {type(paired_index).__name__}")
    low, high = window
    fitted = paired[(paired_index.year >= low) & (paired_index.year <= high)]
    if fitted.empty:
        raise ValueError(f"No overlapping June observations in {low}-{high} to calibrate on")
    return fitted, june.index[0], index.freqstr


def _backcast_stats(fitted: pd.DataFrame, slope: float, intercept: float, earlier: pd.Series) -> dict[str, float]:
    """Summarise the CES-to-survey fit, and the CES range it is projected over."""
    predicted = slope * fitted["ces"] + intercept
    resid = fitted["survey"] - predicted
    total = ((fitted["survey"] - fitted["survey"].mean()) ** 2).sum()
    return {
        "slope": float(slope),
        "intercept": float(intercept),
        "r2": float(1 - (resid**2).sum() / total),
        "resid_sd": float(resid.std(ddof=2)),
        "n": float(len(fitted)),
        "fitted_ces_min": float(fitted["ces"].min()),
        "fitted_ces_max": float(fitted["ces"].max()),
        "projected_ces_min": float(earlier.min()),
        "projected_ces_max": float(earlier.max()),
    }


def _backcast(ces: pd.Series, modellers: pd.Series) -> tuple[pd.Series, dict[str, float]]:
    """Model the survey rate before the Modellers' Database from the CES rate.

    A straight line is fitted from the CES rate to the survey rate over CALIBRATION_YEARS,
    applied to the earlier CES years, and the annual June estimates are joined monthly
    without adding turns. Returns the monthly estimate and the fit statistics.
    """
    fitted, first_june, freq = _june_pairs(ces, modellers, CALIBRATION_YEARS)
    slope, intercept = np.polyfit(fitted["ces"], fitted["survey"], 1)
    earlier = ces[ces.index < first_june]
    estimate = slope * earlier + intercept
    span = pd.period_range(estimate.index[0], estimate.index[-1], freq=freq)
    monthly = estimate.reindex(span).interpolate(method="linear")
    return monthly.rename("Modelled from CES"), _backcast_stats(fitted, slope, intercept, earlier)


@cache
def _unemployment_rate() -> tuple[pd.Series, pd.DataFrame, dict[str, float]]:
    """Splice the rate, survey first (cached; not for mutation): rate, splice report, fit statistics."""
    modellers = _modellers_rate()
    modelled, stats = _backcast(_ces_rate(), modellers)
    rate, report = ra.splice([_lfs_rate(), modellers, modelled], rebase=False, name="Unemployment rate")
    return rate, report, stats


def get_unemployment_rate() -> tuple[pd.Series, str, str]:
    """Return the monthly unemployment rate spliced back to 1950, as (series copy, units, series type)."""
    rate, _report, _stats = _unemployment_rate()
    return rate.copy(), UNITS, STYPE


def get_unemployment_splice_report() -> pd.DataFrame:
    """Return a copy of the ra.splice() audit report (the overlap junctions)."""
    _rate, report, _stats = _unemployment_rate()
    return report.copy()


def get_unemployment_backcast_stats() -> dict[str, float]:
    """Return the CES backcast fit statistics: slope, intercept, r2, resid_sd, n, and the CES ranges.

    The fitted CES range against the projected one is the pair that matters: the further the
    early CES values sit outside the fitted range, the more the 1950s are extrapolation.
    """
    _rate, _report, stats = _unemployment_rate()
    return dict(stats)
