"""Shared pieces of the Modellers' Database module: the data, windows, and the decade-average chart."""

# --- dependencies
import io
from dataclasses import dataclass
from functools import cache

import numpy as np
import pandas as pd
import readabs as ra
from mgplot import line_plot_finalise
from readabs import metacol as mc

from au_econ.charting.footers import SERIES_TYPE_NOTES, data_to
from au_econ.series.gdp import get_gdp
from au_econ.sources.http_cache import get_file

__all__ = ["data_to"]  # re-exported: the module's chart files take it from here

# --- tables and descriptions
KEY_AGGS = "5206001_Key_Aggregates"
INCOME_TABLE = "5206007_Income_From_GDP"
VOLUME_MEASURES = "5206002_Expenditure_Volume_Measures"
MODELLERS = "1364.0.15.003"
MODELLERS_SOURCE = f"ABS: {MODELLERS}"
BOTH_SOURCE = f"ABS: {MODELLERS}, 5206.0"  # the Modellers' Database and the National Accounts
SA = "Seasonally Adjusted"
CAPITAL_DID = "Non-financial and financial corporations ; Net capital stock (Chain volume measures) ;"
PERCENT = 100
QUARTERS_PER_YEAR = 4
HENDERSON_TERMS = 13
LEGEND = {"loc": "best", "fontsize": 9}
COVID_YEARS = (2020, 2021)  # left out of the Okun fits

# --- lfooter notes: "Australia. <series type> <price measure> <chart notes> Data to <period>."
AUSTRALIA = "Australia. "
SA_NOTE = f"{SERIES_TYPE_NOTES[SA]} "
ORIGINAL_NOTE = f"{SERIES_TYPE_NOTES['Original']} "
CVM_NOTE = "Chain volume measures. "
SA_CVM = f"{AUSTRALIA}{SA_NOTE}{CVM_NOTE}"

# --- RBA Occasional Paper 8, table 4.12: aggregate weekly hours, an August snapshot each year
OP8_HOURS_URL = "https://www.rba.gov.au/statistics/xls/op8/4-12.xls"
OP8_HOURS_SHEET = "4.12"
OP8_HOURS_CACHE_PREFIX = "rba_op8_hours"
OP8_YEAR_COL, OP8_TOTAL_COL = 0, 32
AUGUST = 8


@dataclass(frozen=True)
class ModellersData:
    """The National Accounts release, and the shared series: {name: (series, metadata row)}."""

    data: dict[str, pd.DataFrame]
    meta: pd.DataFrame
    source: str
    used: dict[str, tuple[pd.Series, pd.Series]]


def used_often(data: dict[str, pd.DataFrame], meta: pd.DataFrame) -> dict[str, tuple[pd.Series, pd.Series]]:
    """Return the seasonally adjusted series several charts share, each with its metadata row."""
    md_data, md_meta = ra.read_abs_cat(MODELLERS, verbose=False)

    def select(
        frames: dict[str, pd.DataFrame], rows: pd.DataFrame, selector: dict[str, str]
    ) -> tuple[pd.Series, pd.Series]:
        row = ra.search_abs_meta(rows, selector | {SA: mc.stype}, validate_unique=True).iloc[0]
        series = frames[row[mc.table]][row[mc.id]].dropna()
        if series.empty:
            raise ValueError(f"No data for {row[mc.did]}")
        return series, row

    return {
        "gdp_cvm": select(
            data, meta, {KEY_AGGS: mc.table, "Gross domestic product: Chain volume measures ;": mc.did}
        ),
        "hours": select(data, meta, {KEY_AGGS: mc.table, "Hours worked: Index ;": mc.did}),
        "gdp_per_hour": select(data, meta, {KEY_AGGS: mc.table, "GDP per hour worked: Index ;": mc.did}),
        "coe": select(data, meta, {INCOME_TABLE: mc.table, "Compensation of employees ;": mc.did}),
        "capital": select(md_data, md_meta, {CAPITAL_DID: mc.did}),
        "labour_force": select(md_data, md_meta, {"Total labour force ;": mc.did}),
        "unemployed": select(md_data, md_meta, {"Total unemployed ;": mc.did}),
    }


def year_ended_growth(series: pd.Series) -> pd.Series:
    """Return year-ended percentage growth of a quarterly series."""
    return (series / series.shift(QUARTERS_PER_YEAR) - 1) * PERCENT


def is_quarter_end(index: pd.Index) -> np.ndarray:
    """Return True for the months of a monthly PeriodIndex that close a quarter."""
    if not isinstance(index, pd.PeriodIndex):
        raise TypeError(f"Expected a monthly PeriodIndex, got {type(index).__name__}")
    return np.asarray(index == index.asfreq("Q").asfreq("M", how="E"))


def decade_average_plot(
    growth: pd.Series,
    *,
    title: str,
    rfooter: str,
    lfooter: str,
    pre_tag: str,
    tag: str,
    six_to_five: bool = False,
) -> None:
    """Draw year-on-year growth with a decade-average step line (calendar decades, or years ending 6 to 5)."""
    if six_to_five:

        def bucket(year: int) -> int:
            return ((year - 6) // 10) * 10 + 6

        name = "Decade average (6-to-5)"
    else:

        def bucket(year: int) -> int:
            return (year // 10) * 10

        name = "Decade average"
    labels = pd.Series([bucket(p.year) for p in growth.index], index=growth.index)
    averages = growth.groupby(labels).mean()
    step = pd.Series([averages.loc[bucket(p.year)] for p in growth.index], index=growth.index, name=name)
    line_plot_finalise(
        pd.DataFrame({"Annual growth (YoY)": growth, name: step}),
        title=title,
        ylabel="Per cent (YoY)",
        width=[1, 3],
        color=["#888888", "darkred"],
        style=["-", "-"],
        annotate=[False, True],
        rounding=2,
        y0=True,
        legend=LEGEND,
        rfooter=rfooter,
        lfooter=f"{lfooter.rstrip()} {data_to(growth)}",
        pre_tag=pre_tag,
        tag=tag,
    )


# --- GDP per hour worked spliced back to 1966
@cache
def _op8_hours() -> pd.Series:
    """Return aggregate weekly hours worked at August each year, on that quarter (cached; not for mutation)."""
    raw = pd.read_excel(
        io.BytesIO(get_file(OP8_HOURS_URL, prefix=OP8_HOURS_CACHE_PREFIX)), sheet_name=OP8_HOURS_SHEET, header=None
    )
    years = pd.to_numeric(raw[OP8_YEAR_COL].astype(str).str.extract(r"^(\d{4})$")[0], errors="coerce")
    hours = pd.to_numeric(raw[OP8_TOTAL_COL], errors="coerce")
    keep = years.notna() & hours.notna()
    if not keep.any():
        raise ValueError(f"No aggregate hours worked found in {OP8_HOURS_URL}")
    index = pd.PeriodIndex([pd.Period(year=int(y), month=AUGUST, freq="Q") for y in years[keep]], freq="Q")
    return pd.Series(hours[keep].to_numpy(), index=index, name="Aggregate weekly hours")


def _derived_productivity() -> pd.Series:
    """Return real GDP per aggregate weekly hour, the August hours interpolated to quarters (arbitrary scale)."""
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
    """Splice the published GDP per hour worked index over the derived series (cached; not for mutation)."""
    data, meta = ra.read_abs_cat("5206.0", single_excel_only=KEY_AGGS, verbose=False)
    published = ra.select_one(
        data, meta, {KEY_AGGS: mc.table, "GDP per hour worked: Index ;": mc.did, SA: mc.stype}
    ).dropna()
    spliced, report = ra.splice([published, _derived_productivity()], rebase=True)
    return spliced.rename("GDP per hour worked"), report


def get_productivity_index() -> tuple[pd.Series, str, str]:
    """Return GDP per hour worked spliced back to 1966: (series, units, series type).

    The published index (5206.0, unchanged from 1978Q3) over GDP divided by RBA OP8 aggregate
    weekly hours; the derived segment contributes its growth only, rebased onto the published level.
    """
    spliced, _report = _productivity_index()
    return spliced.copy(), "Index Numbers", SA


def get_productivity_splice_report() -> pd.DataFrame:
    """Return the splice report for the productivity index (rebase factor and junction)."""
    _spliced, report = _productivity_index()
    return report.copy()
